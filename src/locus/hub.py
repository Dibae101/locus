"""Locus Hub web UI (Layer 2).

A browsable registry website backed by any ``ImageStore`` (local filesystem today, or
an OCI/Harbor registry when ``LOCUS_REGISTRY`` is set). It lists published images and
shows per-image detail with the data-trust metadata that is Locus's differentiation:
accepted/emitted artifact types, engine modes, privacy class, and provenance
conformance. FastAPI is an optional ``serve`` extra, imported lazily.

Routes:
  GET /                      browse + search images
  GET /images/{name}         image detail (versions + contract)
  GET /api/images            JSON catalog
  GET /api/images/{name}     JSON image detail

Requirements (Hub): browse/search + data-trust metadata display.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from locus.store import ImageStore


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
        images.append(
            {
                "name": name,
                "versions": sorted({s.version for s in summaries}),
                "emits": latest.emits,
                "accepts": latest.accepts,
                "privacy_class": latest.privacy_class.value,
                "provenance_conformant": latest.provenance_conformant,
                "private": latest.private,
            }
        )
    return {"images": images, "count": len(images), "query": query}


def image_detail(store: ImageStore, name: str) -> dict[str, Any]:
    manifest = store.inspect(name)
    versions = sorted({s.version for s in store.search(name) if s.name == name})
    return {
        "name": manifest.name,
        "version": manifest.version,
        "versions": versions or [manifest.version],
        "description": manifest.description,
        "accepts": [a.tag() for a in manifest.accepts] or ["(source)"],
        "emits": manifest.emits.tag(),
        "engine_modes": manifest.engine_modes,
        "privacy_class": manifest.privacy_class.value,
        "provenance_conformant": manifest.provenance_conformant,
    }


# --- HTML rendering -------------------------------------------------------


def render_browse(payload: dict[str, Any]) -> str:
    cards = []
    for img in payload["images"]:
        badge = "✓ grounded" if img["provenance_conformant"] else "⚠ unverified"
        vis = "private" if img["private"] else "public"
        cards.append(
            f'<a class="card" href="/images/{html.escape(img["name"])}">'
            f'<div class="name">{html.escape(img["name"])}</div>'
            f'<div class="types">{html.escape(", ".join(img["accepts"]) or "(source)")} '
            f'&rarr; {html.escape(img["emits"])}</div>'
            f'<div class="tags"><span class="tag">{badge}</span>'
            f'<span class="tag">{vis}</span>'
            f'<span class="tag">{html.escape(img["versions"][-1])}</span></div></a>'
        )
    return _PAGE.format(
        title="Locus Hub",
        body=(
            '<form class="search" method="get">'
            f'<input name="q" placeholder="Search images" value="{html.escape(payload["query"])}">'
            "<button>Search</button></form>"
            f'<div class="count">{payload["count"]} image(s)</div>'
            f'<div class="grid">{"".join(cards) or "<p>No images found.</p>"}</div>'
        ),
    )


def render_detail(d: dict[str, Any]) -> str:
    badge = "✓ provenance-conformant" if d["provenance_conformant"] else "⚠ not conformant"
    rows = [
        ("Description", html.escape(d["description"] or "—")),
        ("Accepts", html.escape(", ".join(d["accepts"]))),
        ("Emits", html.escape(d["emits"])),
        ("Engine modes", html.escape(", ".join(d["engine_modes"]))),
        ("Privacy", html.escape(d["privacy_class"])),
        ("Versions", html.escape(", ".join(d["versions"]))),
        ("Trust", badge),
    ]
    table = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    pull = f"locus pull {html.escape(d['name'])}:{html.escape(d['version'])}"
    return _PAGE.format(
        title=f"{d['name']} — Locus Hub",
        body=(
            f'<a class="back" href="/">&larr; all images</a>'
            f'<h2>{html.escape(d["name"])}</h2>'
            f'<pre class="pull">{pull}</pre>'
            f'<table class="detail">{table}</table>'
        ),
    )


def create_hub_app(store: ImageStore) -> Any:
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise RuntimeError(
            "The Hub UI requires the 'serve' extra: pip install locus[serve]"
        ) from exc

    app = FastAPI(title="Locus Hub")

    @app.get("/", response_class=HTMLResponse)
    def browse(q: str = "") -> str:
        return render_browse(browse_payload(store, q))

    @app.get("/images/{name}", response_class=HTMLResponse)
    def detail(name: str) -> str:
        return render_detail(image_detail(store, name))

    @app.get("/api/images")
    def api_images(q: str = "") -> Any:
        return JSONResponse(browse_payload(store, q))

    @app.get("/api/images/{name}")
    def api_detail(name: str) -> Any:
        return JSONResponse(image_detail(store, name))

    return app


def serve_hub(store: ImageStore, *, host: str = "127.0.0.1", port: int = 8800) -> None:
    import uvicorn

    uvicorn.run(create_hub_app(store), host=host, port=port, log_level="warning")


_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 0; background: #f7f9fc; color: #1f2933; }}
 header {{ background: #1f2933; color: #fff; padding: 1rem 2rem; }}
 header b {{ color: #5fd0c4; }}
 main {{ max-width: 1000px; margin: 0 auto; padding: 2rem; }}
 .search {{ display: flex; gap: 8px; margin-bottom: 1rem; }}
 .search input {{ flex: 1; padding: 8px 12px; border: 1px solid #cbd2d9; border-radius: 6px; }}
 .search button {{ padding: 8px 16px; border: 0; background: #2e8b57; color: #fff; border-radius: 6px; }}
 .count {{ color: #52606d; margin-bottom: 1rem; }}
 .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; }}
 .card {{ display: block; background: #fff; border: 1px solid #e4e7eb; border-radius: 10px; padding: 1rem; text-decoration: none; color: inherit; }}
 .card:hover {{ border-color: #2e8b57; }}
 .card .name {{ font-weight: 600; font-size: 1.05rem; }}
 .card .types {{ color: #52606d; font-size: 0.85rem; margin: 6px 0; }}
 .tag {{ display: inline-block; background: #eef2f7; border-radius: 12px; padding: 2px 10px; font-size: 0.75rem; margin-right: 6px; }}
 table.detail {{ background: #fff; border-collapse: collapse; width: 100%; border-radius: 10px; overflow: hidden; }}
 table.detail th, table.detail td {{ text-align: left; padding: 10px 14px; border-bottom: 1px solid #eef2f7; }}
 table.detail th {{ width: 160px; color: #52606d; }}
 pre.pull {{ background: #1f2933; color: #5fd0c4; padding: 12px 16px; border-radius: 8px; }}
 .back {{ color: #2e8b57; text-decoration: none; }}
</style></head>
<body><header><b>Locus</b> Hub</header><main>{body}</main></body></html>"""
