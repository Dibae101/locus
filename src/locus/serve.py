"""Result serving and preview UI (Layer 2, Stage 9).

Serves a pipeline's final result locally: the rows, each cell's faithfulness score
and originating source location, the flagged rows, and which engine produced the
result. FastAPI is an optional ``serve`` extra; this module imports it lazily so the
core stays light. Everything is local — no hosted service (Req 8.5).

Requirements: 8.1, 8.2, 8.3, 8.5.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from locus.emit_constants import LINEAGE_COLUMN

if TYPE_CHECKING:
    from locus.executor import PipelineRunOutput


def build_result_payload(out: PipelineRunOutput) -> dict[str, Any]:
    """Assemble the JSON payload the UI renders (Req 8.2, 8.3)."""
    frame = out.frame
    data_cols = [c for c in frame.columns if c != LINEAGE_COLUMN]
    rows: list[dict[str, Any]] = []
    for i, prov_row in enumerate(out.provenance):
        cells: dict[str, Any] = {}
        for col in data_cols:
            origin = prov_row.cells.get(col)
            cells[col] = {
                "value": frame.iloc[i][col] if i < len(frame) else None,
                "faithfulness": origin.faithfulness if origin else None,
                "grounding_mode": origin.grounding_mode if origin else "none",
                "source_ids": origin.source_ids if origin else [],
                "lineage_broken": origin.lineage_broken if origin else False,
            }
        rows.append({"flagged": prov_row.flagged, "cells": cells})
    return {
        "columns": data_cols,
        "rows": rows,
        "engine_mode": out.engine_mode,  # Req 8.3
        "row_count": len(rows),
        "flagged_count": sum(1 for r in rows if r["flagged"]),
        "warnings": out.warnings,
        "profiles": build_column_profiles(frame, data_cols),
    }


def build_column_profiles(frame: Any, data_cols: list[str]) -> list[dict[str, Any]]:
    """Per-column profile for the visualization: dtype, fill rate, and either a
    numeric summary (for charts) or a top-value distribution (for categoricals)."""
    import pandas as pd

    profiles: list[dict[str, Any]] = []
    n = len(frame)
    for col in data_cols:
        series = frame[col]
        non_null = int(series.notna().sum())
        numeric = pd.to_numeric(series, errors="coerce")
        numeric_ratio = float(numeric.notna().mean()) if n else 0.0
        prof: dict[str, Any] = {
            "name": col,
            "non_null": non_null,
            "fill_rate": round(non_null / n, 4) if n else 0.0,
            "unique": int(series.nunique(dropna=True)),
        }
        if n and numeric_ratio >= 0.8:
            valid = numeric.dropna()
            prof["kind"] = "numeric"
            prof["min"] = float(valid.min()) if len(valid) else None
            prof["max"] = float(valid.max()) if len(valid) else None
            prof["mean"] = round(float(valid.mean()), 4) if len(valid) else None
            prof["histogram"] = _histogram(valid)
        else:
            prof["kind"] = "categorical"
            counts = series.astype("string").value_counts().head(10)
            prof["top_values"] = [
                {"value": str(idx), "count": int(cnt)} for idx, cnt in counts.items()
            ]
        profiles.append(prof)
    return profiles


def _histogram(values: Any, bins: int = 10) -> list[dict[str, Any]]:
    """Build a small fixed-width histogram for a numeric series."""
    import pandas as pd

    if len(values) == 0:
        return []
    lo, hi = float(values.min()), float(values.max())
    if lo == hi:
        return [{"label": f"{lo:g}", "count": int(len(values))}]
    cut = pd.cut(values, bins=bins)
    grouped = cut.value_counts().sort_index()
    out: list[dict[str, Any]] = []
    for interval, cnt in grouped.items():
        out.append({"label": f"{interval.left:.4g}–{interval.right:.4g}", "count": int(cnt)})
    return out


def render_html(payload: dict[str, Any]) -> str:
    """A minimal, dependency-free HTML view of the result + provenance + charts."""
    cols = payload["columns"]
    head = "".join(f"<th>{c}</th>" for c in cols)
    body_rows = []
    for r in payload["rows"]:
        tds = []
        for c in cols:
            cell = r["cells"][c]
            f = cell["faithfulness"]
            score = "—" if f is None else f"{f:.2f}"
            broken = " broken" if cell["lineage_broken"] else ""
            srcs = ", ".join(cell["source_ids"]) or "n/a"
            title = f"source: {srcs} | grounding: {cell['grounding_mode']}"
            tds.append(
                f'<td class="cell{broken}" title="{title}">'
                f'{cell["value"]}<span class="score">{score}</span></td>'
            )
        cls = "flagged" if r["flagged"] else ""
        body_rows.append(f'<tr class="{cls}">{"".join(tds)}</tr>')
    return _HTML_TEMPLATE.format(
        engine=payload["engine_mode"],
        rows=payload["row_count"],
        flagged=payload["flagged_count"],
        head=head,
        body="".join(body_rows),
        charts=_render_charts(payload.get("profiles", [])),
        payload_json=json.dumps(payload, default=str),
    )


def _render_charts(profiles: list[dict[str, Any]]) -> str:
    """Render per-column profile cards with CSS bar charts (no JS dependency)."""
    if not profiles:
        return ""
    cards = []
    for p in profiles:
        meta = (
            f'<div class="cmeta">{p["kind"]} &middot; '
            f'fill {p["fill_rate"] * 100:.0f}% &middot; {p["unique"]} unique</div>'
        )
        if p["kind"] == "numeric":
            stats = (
                f'<div class="cstats">min {_fmt(p["min"])} &middot; '
                f'mean {_fmt(p["mean"])} &middot; max {_fmt(p["max"])}</div>'
            )
            bars = _bar_chart(
                [(b["label"], b["count"]) for b in p.get("histogram", [])]
            )
        else:
            stats = ""
            bars = _bar_chart(
                [(v["value"], v["count"]) for v in p.get("top_values", [])]
            )
        cards.append(
            f'<div class="card"><h3>{_esc(p["name"])}</h3>{meta}{stats}{bars}</div>'
        )
    return f'<section class="charts">{"".join(cards)}</section>'


def _bar_chart(items: list[tuple[str, int]]) -> str:
    if not items:
        return '<div class="empty">no data</div>'
    peak = max((c for _, c in items), default=1) or 1
    rows = []
    for label, count in items:
        pct = int(round(100 * count / peak))
        rows.append(
            f'<div class="bar-row"><span class="bar-label" title="{_esc(label)}">'
            f'{_esc(label)}</span><span class="bar-track">'
            f'<span class="bar-fill" style="width:{pct}%"></span></span>'
            f'<span class="bar-count">{count}</span></div>'
        )
    return f'<div class="bars">{"".join(rows)}</div>'


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def _esc(text: Any) -> str:
    import html

    return html.escape(str(text))


def create_app(out: PipelineRunOutput) -> Any:  # returns a FastAPI app
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise RuntimeError(
            "Serving requires the 'serve' extra: pip install 'locus-etl[serve]'"
        ) from exc

    payload = build_result_payload(out)
    app = FastAPI(title="Locus Result")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render_html(payload)

    @app.get("/api/result")
    def result() -> Any:
        return JSONResponse(payload)

    return app


def serve_result(
    out: PipelineRunOutput,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = False,
) -> None:
    """Serve the result on a local port (Req 8.1). Blocks until interrupted."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise RuntimeError(
            "Visualization requires the 'serve' extra: pip install 'locus-etl[serve]' "
            "(or 'locus-etl[standard]')"
        ) from exc

    app = create_app(out)  # validates FastAPI presence with the same guidance

    if open_browser:
        import threading
        import webbrowser

        url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}"  # noqa: S104
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")


_HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Locus Result</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1f2933; }}
 h1 {{ margin-bottom: 0.25rem; }}
 .meta {{ color: #52606d; margin-bottom: 1.5rem; }}
 h2 {{ font-size: 1.1rem; color: #334e68; border-bottom: 1px solid #d9e2ec;
       padding-bottom: 4px; margin-top: 2rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #d9e2ec; padding: 6px 10px; text-align: left; }}
 th {{ background: #f0f4f8; }}
 tr.flagged {{ background: #fff7ed; }}
 td.broken {{ background: #fde8e8; }}
 .score {{ color: #829ab1; font-size: 0.8em; margin-left: 6px; }}
 .charts {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1rem; }}
 .card {{ border: 1px solid #d9e2ec; border-radius: 8px; padding: 12px 14px;
          background: #fff; }}
 .card h3 {{ margin: 0 0 4px; font-size: 0.95rem; }}
 .cmeta, .cstats {{ color: #627d98; font-size: 0.78rem; margin-bottom: 6px; }}
 .bar-row {{ display: flex; align-items: center; gap: 6px; margin: 3px 0;
             font-size: 0.78rem; }}
 .bar-label {{ width: 90px; overflow: hidden; text-overflow: ellipsis;
               white-space: nowrap; color: #486581; }}
 .bar-track {{ flex: 1; background: #f0f4f8; border-radius: 3px; height: 12px; }}
 .bar-fill {{ display: block; height: 12px; border-radius: 3px; background: #3ebd93; }}
 .bar-count {{ width: 44px; text-align: right; color: #627d98; }}
 .empty {{ color: #9aa5b1; font-size: 0.8rem; }}
</style></head>
<body>
 <h1>Locus Result</h1>
 <div class="meta">engine: <b>{engine}</b> &middot; rows: {rows} &middot; flagged: {flagged}
   &middot; hover a cell for source &amp; grounding</div>
 <h2>Visualize</h2>
 {charts}
 <h2>Data &amp; provenance</h2>
 <table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
</body></html>"""
