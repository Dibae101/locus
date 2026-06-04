"""Tests for the Locus image catalog."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from locus.catalog import CATALOG, all_images, resolve_catalog
from locus.catalog.transforms import (
    _AnomalyFlagger,
    _DataCleaner,
    _Deduplicator,
    _PiiRedactor,
)
from locus.emit_constants import LINEAGE_COLUMN
from locus.image import StageContext
from locus.locusfile import Locusfile, SourceSpec, StageSpec
from locus.runner import resolve_image, run_pipeline
from locus.workspace import RunWorkspace

CSV = str(Path(__file__).parent.parent / "fixtures" / "invoices.csv")


def _frame_with_lineage() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "name": ["a@x.com", "  Bob  ", "a@x.com"],
            "amount": ["10", "20", "10"],
            LINEAGE_COLUMN: [
                {"_row_flagged": False, "name": {"locations": [{"source_id": "s"}]}},
                {"_row_flagged": False, "name": {"locations": [{"source_id": "s"}]}},
                {"_row_flagged": False, "name": {"locations": [{"source_id": "s"}]}},
            ],
        }
    )


def _ctx(**cfg: object) -> StageContext:
    return StageContext(stage_id="t", source=None, config=dict(cfg))


def test_catalog_has_expected_images() -> None:
    for name in ["doc-to-tables", "invoice-extractor", "any-to-json", "pii-redactor",
                 "deduplicator", "data-cleaner", "anomaly-flagger"]:
        assert name in CATALOG


def test_all_images_resolve_with_valid_manifests() -> None:
    images = all_images()
    assert len(images) == len(CATALOG)
    for img in images:
        assert img.manifest.version
        assert img.manifest.emits.tag() == "table/v1"
        assert img.manifest.provenance_conformant is True


def test_resolve_catalog_by_ref() -> None:
    img = resolve_catalog("invoice-extractor:0.1.0")
    assert img is not None and img.manifest.name == "invoice-extractor"
    assert resolve_catalog("nonexistent") is None


def test_resolve_image_prefers_catalog() -> None:
    assert resolve_image("doc-to-tables:0.1.0").manifest.name == "doc-to-tables"


# --- individual capabilities ---------------------------------------------


def test_pii_redactor_masks_email() -> None:
    out, _ = _PiiRedactor().run([_frame_with_lineage()], _ctx())
    assert "[EMAIL]" in out["name"].tolist()
    assert LINEAGE_COLUMN in out.columns  # provenance preserved


def test_data_cleaner_trims_whitespace() -> None:
    out, _ = _DataCleaner().run([_frame_with_lineage()], _ctx())
    assert "Bob" in out["name"].tolist()


def test_deduplicator_removes_duplicates() -> None:
    out, _ = _Deduplicator().run([_frame_with_lineage()], _ctx(keys=["name", "amount"]))
    assert len(out) == 2


def test_anomaly_flagger_flags_outlier() -> None:
    frame = pd.DataFrame(
        {
            "v": [1, 1, 1, 1, 1000],
            LINEAGE_COLUMN: [{"_row_flagged": False} for _ in range(5)],
        }
    )
    out, _ = _AnomalyFlagger().run([frame], _ctx())
    flags = [lin.get("_row_flagged") for lin in out[LINEAGE_COLUMN]]
    assert flags[-1] is True


# --- composition with the engine -----------------------------------------


def test_extract_then_redact_pipeline_preserves_provenance() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[
            StageSpec(id="extract", image="doc-to-tables:0.1.0"),
            StageSpec(id="redact", image="pii-redactor:0.1.0", needs=["extract"]),
        ],
    )
    out = run_pipeline(lf, workspace=RunWorkspace())
    assert len(out.frame) == 3
    # provenance survives the redaction stage
    assert all(
        any(s.endswith("invoices.csv") for s in row.origin_source_ids)
        for row in out.provenance
    )


def test_convert_pipeline_runs() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[
            StageSpec(id="extract", image="doc-to-tables:0.1.0"),
            StageSpec(id="json", image="any-to-json:0.1.0", needs=["extract"]),
        ],
    )
    out = run_pipeline(lf, workspace=RunWorkspace())
    assert len(out.frame) == 3
