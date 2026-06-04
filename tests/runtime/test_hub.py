"""Tests for the Locus Hub web UI (multi-page site + docs).

Skips gracefully if the 'serve' extra (FastAPI) is not installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from locus.hub import (  # noqa: E402
    browse_payload,
    create_hub_app,
    image_detail,
    render_browse,
    render_home,
    render_markdown,
)
from locus.hub_docs import PAGES  # noqa: E402
from locus.seed import seed_catalog  # noqa: E402
from locus.store import LocalImageStore  # noqa: E402


def _seeded_store(tmp_path: Path) -> LocalImageStore:
    store = LocalImageStore(root=tmp_path / "registry")
    seed_catalog(store)
    return store


def test_browse_payload_includes_summaries(tmp_path: Path) -> None:
    payload = browse_payload(_seeded_store(tmp_path))
    names = {img["name"] for img in payload["images"]}
    assert "doc-to-tables" in names and "pii-redactor" in names
    pii = next(i for i in payload["images"] if i["name"] == "pii-redactor")
    assert pii["summary"]  # doc summary present
    assert pii["tier"]


def test_image_detail_has_docs_and_example(tmp_path: Path) -> None:
    d = image_detail(_seeded_store(tmp_path), "pii-redactor")
    assert d["emits"] == "table/v1"
    assert d["provenance_conformant"] is True
    assert d["details"]
    assert "locus" not in d["example_locusfile"].split("\n")[0]  # yaml, not a command
    assert "pii-redactor" in d["example_locusfile"]


def test_render_home_and_browse(tmp_path: Path) -> None:
    home = render_home(16)
    assert "Locus" in home and "Browse 16 images" in home
    browse = render_browse(browse_payload(_seeded_store(tmp_path)))
    assert "doc-to-tables" in browse and "Search" in browse


def test_markdown_renderer() -> None:
    out = render_markdown("# Title\n\nSome `code` here.\n\n- one\n- two\n")
    assert "<h1>Title</h1>" in out
    assert "<code>code</code>" in out
    assert "<li>one</li>" in out


def test_hub_app_routes(tmp_path: Path) -> None:
    client = TestClient(create_hub_app(_seeded_store(tmp_path)))

    assert client.get("/").status_code == 200
    assert "Locus" in client.get("/").text

    cat = client.get("/catalog")
    assert cat.status_code == 200 and "doc-to-tables" in cat.text

    detail = client.get("/images/doc-to-tables")
    assert detail.status_code == 200 and "Example Locusfile" in detail.text

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "Documentation" in docs.text  # our page, not FastAPI's Swagger UI
    assert "swagger" not in docs.text.lower()
    for page in PAGES:
        r = client.get(f"/docs/{page.slug}")
        assert r.status_code == 200, page.slug
        assert page.title in r.text

    assert client.get("/docs/nonexistent").status_code == 404
    assert client.get("/images/nope").status_code == 404

    api = client.get("/api/images")
    assert api.status_code == 200 and api.json()["count"] > 0


def test_docs_pages_have_content() -> None:
    assert len(PAGES) >= 5
    for page in PAGES:
        assert page.body.strip()
        assert page.slug and page.title
