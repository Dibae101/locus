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
    }


def render_html(payload: dict[str, Any]) -> str:
    """A minimal, dependency-free HTML view of the result + provenance."""
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
        payload_json=json.dumps(payload, default=str),
    )


def create_app(out: PipelineRunOutput) -> Any:  # returns a FastAPI app
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise RuntimeError(
            "Serving requires the 'serve' extra: pip install locus[serve]"
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


def serve_result(out: PipelineRunOutput, *, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Serve the result on a local port (Req 8.1). Blocks until interrupted."""
    import uvicorn

    uvicorn.run(create_app(out), host=host, port=port, log_level="warning")


_HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Locus Result</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1f2933; }}
 .meta {{ color: #52606d; margin-bottom: 1rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #d9e2ec; padding: 6px 10px; text-align: left; }}
 th {{ background: #f0f4f8; }}
 tr.flagged {{ background: #fff7ed; }}
 td.broken {{ background: #fde8e8; }}
 .score {{ color: #829ab1; font-size: 0.8em; margin-left: 6px; }}
</style></head>
<body>
 <h1>Locus Result</h1>
 <div class="meta">engine: <b>{engine}</b> &middot; rows: {rows} &middot; flagged: {flagged}
   &middot; hover a cell for source &amp; grounding</div>
 <table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
</body></html>"""
