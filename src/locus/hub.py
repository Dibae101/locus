"""Locus Hub web UI (Layer 2).

A browsable registry website + user documentation, backed by any ``ImageStore``
(local filesystem, or an OCI/Harbor registry when ``LOCUS_REGISTRY`` is set). It is a
multi-page site (home, catalog browse/search, per-image docs, and a docs section)
modeled on Docker Hub + Docker docs. FastAPI is an optional ``serve`` extra, imported
lazily.

Routes:
  GET /                      landing page
  GET /catalog               browse + search images
  GET /images/{name}         image detail (contract + docs + usage)
  GET /docs                  docs index
  GET /docs/{slug}           a docs page
  GET /api/images            JSON catalog
  GET /api/images/{name}     JSON image detail
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING, Any

from locus.catalog.docs import example_locusfile, get_doc
from locus.hub_docs import PAGES, PAGES_BY_SLUG

if TYPE_CHECKING:
    from locus.store import ImageStore

VERSION_LABEL = "0.0.2"


# --- data assembly --------------------------------------------------------


def _grouped(store: ImageStore, query: str = "") -> dict[str, list[Any]]:
    groups: dict[str, list[Any]] = {}
    for s in store.search(query):
        groups.setdefault(s.name, []).append(s)
    return groups


def browse_payload(store: ImageStore, query: str = "") -> dict[str, Any]:
    groups = _grouped(store, query)
    images = []
    for name, summaries in sorted(groups.items()):
        latest = sorted(summaries, key=lambda s: s.version)[-1]
        doc = get_doc(name)
        images.append(
            {
                "name": name,
                "versions": sorted({s.version for s in summaries}),
                "emits": latest.emits,
                "accepts": latest.accepts,
                "privacy_class": latest.privacy_class.value,
                "provenance_conformant": latest.provenance_conformant,
                "private": latest.private,
                "summary": doc.summary,
                "tier": doc.tier,
            }
        )
    return {"images": images, "count": len(images), "query": query}


def image_detail(store: ImageStore, name: str) -> dict[str, Any]:
    manifest = store.inspect(name)
    versions = sorted({s.version for s in store.search(name) if s.name == name})
    doc = get_doc(name)
    return {
        "name": manifest.name,
        "version": manifest.version,
        "versions": versions or [manifest.version],
        "description": manifest.description,
        "summary": doc.summary,
        "details": doc.details,
        "examples": doc.examples,
        "tier": doc.tier,
        "accepts": [a.tag() for a in manifest.accepts] or ["(source)"],
        "emits": manifest.emits.tag(),
        "engine_modes": manifest.engine_modes,
        "privacy_class": manifest.privacy_class.value,
        "provenance_conformant": manifest.provenance_conformant,
        "example_locusfile": example_locusfile(name),
    }


# --- tiny markdown renderer (headings, code fences, lists, paragraphs) -----


def render_markdown(md: str) -> str:
    lines = md.strip("\n").split("\n")
    out: list[str] = []
    in_code = False
    in_list = False
    buf: list[str] = []

    def flush_para() -> None:
        nonlocal buf
        if buf:
            out.append("<p>" + _inline(" ".join(buf)) + "</p>")
            buf = []

    for line in lines:
        if line.strip().startswith("```"):
            flush_para()
            if not in_code:
                out.append('<pre class="code">')
                in_code = True
            else:
                out.append("</pre>")
                in_code = False
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if line.startswith("### "):
            flush_para()
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            flush_para()
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            flush_para()
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.strip().startswith("- "):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line.strip()[2:])}</li>")
            continue
        elif not line.strip():
            flush_para()
        else:
            buf.append(line.strip())
        if in_list and not line.strip().startswith("- "):
            out.append("</ul>")
            in_list = False
    flush_para()
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


# --- page rendering -------------------------------------------------------


def _layout(title: str, body: str, active: str = "") -> str:
    def nav(label: str, href: str, key: str) -> str:
        cls = "active" if active == key else ""
        return f'<a class="{cls}" href="{href}">{label}</a>'

    navbar = (
        nav("Home", "/", "home")
        + nav("Catalog", "/catalog", "catalog")
        + nav("Docs", "/docs", "docs")
    )
    return _PAGE.format(title=html.escape(title), nav=navbar, body=body, version=VERSION_LABEL)


def render_home(count: int) -> str:
    body = f"""
    <section class="hero">
      <h1>Locus Hub</h1>
      <p class="tagline">Pull a data operation, point it at your data, get a
      <b>source-grounded</b> table. Every cell traces back to where it came from.</p>
      <pre class="code">pip install locus-etl
locus catalog list
locus run locusfile.yaml</pre>
      <div class="cta">
        <a class="btn" href="/catalog">Browse {count} images &rarr;</a>
        <a class="btn ghost" href="/docs/getting-started">Get started</a>
      </div>
    </section>
    <section class="features">
      <div class="feature"><h3>Grounded</h3><p>Per-cell provenance + faithfulness
        scores. Trustworthy by construction.</p></div>
      <div class="feature"><h3>Composable</h3><p>Chain images into typed pipelines;
        provenance survives every stage.</p></div>
      <div class="feature"><h3>Local-first</h3><p>Runs as a plain process. LLM is
        opt-in; your data stays put by default.</p></div>
    </section>
    """
    return _layout("Locus Hub", body, "home")


def render_browse(payload: dict[str, Any]) -> str:
    cards = []
    for img in payload["images"]:
        badge = "✓ grounded" if img["provenance_conformant"] else "⚠ unverified"
        vis = "private" if img["private"] else "public"
        summary = html.escape(img["summary"] or "")
        cards.append(
            f'<a class="card" href="/images/{html.escape(img["name"])}">'
            f'<div class="name">{html.escape(img["name"])}</div>'
            f'<div class="summary">{summary}</div>'
            f'<div class="types">{html.escape(", ".join(img["accepts"]))} '
            f'&rarr; {html.escape(img["emits"])}</div>'
            f'<div class="tags"><span class="tag ok">{badge}</span>'
            f'<span class="tag">{vis}</span>'
            f'<span class="tag">{html.escape(img["versions"][-1])}</span></div></a>'
        )
    body = (
        '<form class="search" method="get" action="/catalog">'
        f'<input name="q" placeholder="Search images…" value="{html.escape(payload["query"])}">'
        "<button>Search</button></form>"
        f'<div class="count">{payload["count"]} image(s)</div>'
        f'<div class="grid">{"".join(cards) or "<p>No images found.</p>"}</div>'
    )
    return _layout("Catalog — Locus Hub", body, "catalog")


def render_detail(d: dict[str, Any]) -> str:
    badge = "✓ provenance-conformant" if d["provenance_conformant"] else "⚠ not conformant"
    rows = [
        ("Accepts", html.escape(", ".join(d["accepts"]))),
        ("Emits", html.escape(d["emits"])),
        ("Engine modes", html.escape(", ".join(d["engine_modes"]))),
        ("Privacy", html.escape(d["privacy_class"])),
        ("Versions", html.escape(", ".join(d["versions"]))),
        ("Trust", badge),
    ]
    table = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    examples = ""
    if d["examples"]:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in d["examples"])
        examples = f"<h3>Common uses</h3><ul>{items}</ul>"
    tier = f'<span class="pill">{html.escape(d["tier"])}</span>' if d["tier"] else ""
    body = (
        f'<a class="back" href="/catalog">&larr; catalog</a>'
        f'<h1>{html.escape(d["name"])} {tier}</h1>'
        f'<p class="summary">{html.escape(d["summary"] or d["description"])}</p>'
        "<h3>Pull</h3>"
        f'<pre class="code">locus pull {html.escape(d["name"])}:{html.escape(d["version"])}</pre>'
        f'<h3>About</h3><p>{html.escape(d["details"])}</p>'
        f"{examples}"
        "<h3>Example Locusfile</h3>"
        f'<pre class="code">{html.escape(d["example_locusfile"])}</pre>'
        "<h3>Run it</h3>"
        '<pre class="code">locus run locusfile.yaml --export out.csv</pre>'
        f'<h3>Contract</h3><table class="detail">{table}</table>'
    )
    return _layout(f"{d['name']} — Locus Hub", body, "catalog")


def render_docs_index() -> str:
    items = "".join(
        f'<li><a href="/docs/{p.slug}">{html.escape(p.title)}</a></li>' for p in PAGES
    )
    body = f"<h1>Documentation</h1><ul class=\"doclist\">{items}</ul>"
    return _layout("Docs — Locus Hub", body, "docs")


def render_doc_page(slug: str) -> str:
    page = PAGES_BY_SLUG[slug]
    side = "".join(
        f'<a class="{"active" if p.slug == slug else ""}" href="/docs/{p.slug}">'
        f"{html.escape(p.title)}</a>"
        for p in PAGES
    )
    body = (
        f'<div class="docwrap"><nav class="docnav">{side}</nav>'
        f'<article class="docbody">{render_markdown(page.body)}</article></div>'
    )
    return _layout(f"{page.title} — Locus Hub", body, "docs")


# --- app ------------------------------------------------------------------


def create_hub_app(store: ImageStore) -> Any:
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise RuntimeError(
            "The Hub UI requires the 'serve' extra: pip install locus-etl[serve]"
        ) from exc

    app = FastAPI(title="Locus Hub", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return render_home(browse_payload(store)["count"])

    @app.get("/catalog", response_class=HTMLResponse)
    def catalog(q: str = "") -> str:
        return render_browse(browse_payload(store, q))

    @app.get("/images/{name}", response_class=HTMLResponse)
    def detail(name: str) -> str:
        try:
            return render_detail(image_detail(store, name))
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"image {name!r} not found") from exc

    @app.get("/docs", response_class=HTMLResponse)
    def docs_index() -> str:
        return render_docs_index()

    @app.get("/docs/{slug}", response_class=HTMLResponse)
    def docs_page(slug: str) -> str:
        if slug not in PAGES_BY_SLUG:
            raise HTTPException(status_code=404, detail=f"doc {slug!r} not found")
        return render_doc_page(slug)

    @app.get("/api/images")
    def api_images(q: str = "") -> Any:
        return JSONResponse(browse_payload(store, q))

    @app.get("/api/images/{name}")
    def api_detail(name: str) -> Any:
        try:
            return JSONResponse(image_detail(store, name))
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


def serve_hub(store: ImageStore, *, host: str = "127.0.0.1", port: int = 8800) -> None:
    import uvicorn

    uvicorn.run(create_hub_app(store), host=host, port=port, log_level="warning")


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
 :root {{ --ink:#1f2933; --muted:#52606d; --line:#e4e7eb; --bg:#f7f9fc; --brand:#2e8b57; --accent:#5fd0c4; }}
 * {{ box-sizing:border-box; }}
 body {{ font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; margin:0; background:var(--bg); color:var(--ink); }}
 header {{ background:#1f2933; color:#fff; display:flex; align-items:center; gap:24px; padding:0 2rem; height:56px; }}
 header .brand {{ font-weight:700; font-size:1.15rem; }}
 header .brand b {{ color:var(--accent); }}
 header nav {{ display:flex; gap:18px; margin-left:8px; }}
 header nav a {{ color:#cbd2d9; text-decoration:none; font-size:.95rem; padding:4px 2px; border-bottom:2px solid transparent; }}
 header nav a:hover {{ color:#fff; }}
 header nav a.active {{ color:#fff; border-bottom-color:var(--accent); }}
 header .ver {{ margin-left:auto; color:#7b8794; font-size:.8rem; }}
 main {{ max-width:1040px; margin:0 auto; padding:2rem; }}
 h1 {{ font-size:1.7rem; }} h2 {{ margin-top:1.6rem; }} h3 {{ margin-top:1.3rem; }}
 a {{ color:var(--brand); }}
 pre.code {{ background:#1f2933; color:var(--accent); padding:14px 16px; border-radius:8px; overflow-x:auto; font-size:.9rem; }}
 code {{ background:#eef2f7; padding:1px 6px; border-radius:5px; font-size:.9em; }}
 .hero {{ text-align:center; padding:2rem 0 1rem; }}
 .hero .tagline {{ color:var(--muted); font-size:1.1rem; max-width:640px; margin:0 auto 1rem; }}
 .hero pre.code {{ text-align:left; max-width:420px; margin:1rem auto; }}
 .cta {{ margin-top:1rem; }}
 .btn {{ display:inline-block; background:var(--brand); color:#fff; padding:10px 18px; border-radius:8px; text-decoration:none; margin:0 6px; }}
 .btn.ghost {{ background:transparent; color:var(--brand); border:1px solid var(--brand); }}
 .features {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:1rem; margin-top:2rem; }}
 .feature {{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:1.2rem; }}
 .feature h3 {{ margin:0 0 .4rem; }}
 .search {{ display:flex; gap:8px; margin-bottom:1rem; }}
 .search input {{ flex:1; padding:10px 12px; border:1px solid #cbd2d9; border-radius:8px; }}
 .search button {{ padding:10px 18px; border:0; background:var(--brand); color:#fff; border-radius:8px; cursor:pointer; }}
 .count {{ color:var(--muted); margin-bottom:1rem; }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:1rem; }}
 .card {{ display:block; background:#fff; border:1px solid var(--line); border-radius:10px; padding:1rem; text-decoration:none; color:inherit; }}
 .card:hover {{ border-color:var(--brand); box-shadow:0 2px 10px rgba(0,0,0,.05); }}
 .card .name {{ font-weight:600; font-size:1.05rem; }}
 .card .summary {{ color:var(--ink); font-size:.9rem; margin:6px 0; }}
 .card .types {{ color:var(--muted); font-size:.8rem; }}
 .tag {{ display:inline-block; background:#eef2f7; border-radius:12px; padding:2px 10px; font-size:.72rem; margin:6px 6px 0 0; }}
 .tag.ok {{ background:#e3f4ea; color:#1c6b40; }}
 .pill {{ font-size:.7rem; background:#eef2f7; color:var(--muted); border-radius:10px; padding:3px 10px; vertical-align:middle; }}
 table.detail {{ background:#fff; border-collapse:collapse; width:100%; border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
 table.detail th, table.detail td {{ text-align:left; padding:10px 14px; border-bottom:1px solid #eef2f7; }}
 table.detail th {{ width:160px; color:var(--muted); }}
 .summary {{ color:var(--muted); font-size:1.05rem; }}
 .back {{ color:var(--brand); text-decoration:none; }}
 .doclist a {{ font-size:1.05rem; }}
 .docwrap {{ display:grid; grid-template-columns:200px 1fr; gap:2rem; }}
 .docnav {{ display:flex; flex-direction:column; gap:6px; }}
 .docnav a {{ color:var(--muted); text-decoration:none; padding:4px 0; }}
 .docnav a.active {{ color:var(--brand); font-weight:600; }}
 .docbody h1 {{ margin-top:0; }}
 @media (max-width:720px) {{ .docwrap {{ grid-template-columns:1fr; }} }}
</style></head>
<body>
 <header>
   <span class="brand"><b>Locus</b> Hub</span>
   <nav>{nav}</nav>
   <span class="ver">v{version}</span>
 </header>
 <main>{body}</main>
</body></html>"""
