"""Tests for the Locus Hub web UI.

Skips gracefully if the 'serve' extra (FastAPI) is not installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from locus.hub import browse_payload, create_hub_app, image_detail, render_browse  # noqa: E402
from locus.seed import seed_catalog  # noqa: E402
from locus.store import LocalImageStore  # noqa: E402


def _seeded_store(tmp_path: Path) -> LocalImageStore:
    store = LocalImageStore(root=tmp_path / "registry")
    seed_catalog(store)
    return store


def test_browse_payload_lists_catalog(tmp_path: Path) -> None:
    payload = browse_payload(_seeded_store(tmp_path))
    names = {img["name"] for img in payload["images"]}
    assert "doc-to-tables" in names
    assert "pii-redactor" in names
    assert payload["count"] == len(payload["images"])


def test_browse_payload_search_filters(tmp_path: Path) -> None:
    payload = browse_payload(_seeded_store(tmp_path), "invoice")
    assert all("invoice" in img["name"] for img in payload["images"])


def test_image_detail_has_trust_metadata(tmp_path: Path) -> None:
    d = image_detail(_seeded_store(tmp_path), "pii-redactor")
    assert d["emits"] == "table/v1"
    assert d["provenance_conformant"] is True
    assert "deterministic" in d["engine_modes"]


def test_render_browse_html(tmp_path: Path) -> None:
    html = render_browse(browse_payload(_seeded_store(tmp_path)))
    assert "Locus" in html and "Hub" in html
    assert "doc-to-tables" in html


def test_hub_app_routes(tmp_path: Path) -> None:
    client = TestClient(create_hub_app(_seeded_store(tmp_path)))

    home = client.get("/")
    assert home.status_code == 200
    assert "Locus" in home.text

    api = client.get("/api/images")
    assert api.status_code == 200
    assert api.json()["count"] > 0

    detail = client.get("/images/doc-to-tables")
    assert detail.status_code == 200
    assert "doc-to-tables" in detail.text

    api_detail = client.get("/api/images/pii-redactor")
    assert api_detail.status_code == 200
    assert api_detail.json()["provenance_conformant"] is True
