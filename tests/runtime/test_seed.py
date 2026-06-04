"""Tests for catalog seeding (Layer 2)."""

from __future__ import annotations

from pathlib import Path

from locus.catalog import CATALOG
from locus.seed import catalog_names, seed_catalog
from locus.store import LocalImageStore


def test_seed_publishes_every_catalog_image(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "registry")
    refs = seed_catalog(store)
    assert len(refs) == len(CATALOG)
    # every seeded image is discoverable and pullable
    found = {s.name for s in store.search()}
    assert found == set(CATALOG)


def test_seeded_image_is_pullable_and_inspectable(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "registry")
    seed_catalog(store)
    path = store.pull("pii-redactor:0.1.0")
    assert (path / "manifest.json").exists()
    m = store.inspect("pii-redactor:0.1.0")
    assert m.name == "pii-redactor"
    assert m.provenance_conformant is True


def test_catalog_names_sorted() -> None:
    names = catalog_names()
    assert names == sorted(names)
    assert "doc-to-tables" in names
