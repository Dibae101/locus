"""Tests for image building + conformance certification + publish (Stage 7)."""

from __future__ import annotations

from pathlib import Path

from locus.builder import build_image, certify_conformance, load_manifest
from locus.builtins import drop_flagged, strip_lineage
from locus.packaging import read_manifest
from locus.store import LocalImageStore

MANIFEST_YAML = """
name: my-image
version: 1.2.0
emits:
  kind: table
  major: 1
accepts:
  - kind: table
    major: 1
engine_modes: [deterministic]
privacy_class: local_only
entrypoint: my_pkg:run
"""


def test_load_manifest(tmp_path: Path) -> None:
    mp = tmp_path / "locus.image.yaml"
    mp.write_text(MANIFEST_YAML)
    m = load_manifest(mp)
    assert m.name == "my-image"
    assert m.emits.tag() == "table/v1"


def test_certify_conformant_capability() -> None:
    # drop-flagged preserves the lineage column -> conformant
    assert certify_conformance(drop_flagged().capability) is True


def test_certify_non_conformant_capability() -> None:
    # strip-lineage drops the lineage column -> non-conformant
    assert certify_conformance(strip_lineage().capability) is False


def test_build_pins_versions_and_certifies(tmp_path: Path) -> None:
    mp = tmp_path / "locus.image.yaml"
    mp.write_text(MANIFEST_YAML)
    out = build_image(
        mp, capability=drop_flagged().capability, output_dir=tmp_path / "built"
    )
    m = read_manifest(out)
    assert m.provenance_conformant is True
    assert "python" in m.dependencies
    assert "pydantic" in m.dependencies


def test_build_then_push_then_search(tmp_path: Path) -> None:
    mp = tmp_path / "locus.image.yaml"
    mp.write_text(MANIFEST_YAML)
    built = build_image(mp, capability=drop_flagged().capability, output_dir=tmp_path / "b")

    store = LocalImageStore(root=tmp_path / "reg")
    ref = store.push(built, private=True)
    assert ref == "my-image:1.2.0"

    results = store.search()
    assert len(results) == 1
    assert results[0].private is True
    assert results[0].provenance_conformant is True
