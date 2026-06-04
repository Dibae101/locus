"""Tests for the result serving / preview UI (Stage 9).

Skips gracefully if the 'serve' extra (FastAPI) is not installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from locus.locusfile import Locusfile, SourceSpec  # noqa: E402
from locus.runner import run_pipeline  # noqa: E402
from locus.serve import build_result_payload, create_app, render_html  # noqa: E402
from locus.workspace import RunWorkspace  # noqa: E402

CSV = str(Path(__file__).parent.parent / "fixtures" / "invoices.csv")


def _run():
    lf = Locusfile(image="doc-to-tables:0.1.0", source=SourceSpec(type="files", path=CSV))
    return run_pipeline(lf, workspace=RunWorkspace())


def test_payload_has_rows_provenance_and_engine_mode() -> None:
    payload = build_result_payload(_run())
    assert payload["columns"] == ["invoice_number", "vendor", "total"]
    assert payload["row_count"] == 3
    assert payload["engine_mode"] == "deterministic"
    cell = payload["rows"][0]["cells"]["vendor"]
    assert "faithfulness" in cell
    assert any(s.endswith("invoices.csv") for s in cell["source_ids"])


def test_render_html_contains_table() -> None:
    html = render_html(build_result_payload(_run()))
    assert "<table" in html
    assert "invoice_number" in html
    assert "engine:" in html


def test_app_serves_index_and_api() -> None:
    client = TestClient(create_app(_run()))
    r = client.get("/")
    assert r.status_code == 200
    assert "Locus Result" in r.text

    api = client.get("/api/result")
    assert api.status_code == 200
    data = api.json()
    assert data["row_count"] == 3
    assert data["engine_mode"] == "deterministic"
