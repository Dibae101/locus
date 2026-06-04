"""The Locus image catalog.

A curated set of capability images built on the Layer 1 engine. Each entry pairs an
``ImageManifest`` with a runnable capability. Root images (source -> table) wrap the
engine pipeline; transform images (table -> table) operate on the result frame while
preserving the per-cell ``_lineage`` column so provenance survives composition.

``CATALOG`` maps image name -> factory. ``resolve_catalog(ref)`` returns a
``ResolvedImage`` for a ``name[:version]`` reference.
"""

from __future__ import annotations

from collections.abc import Callable

from locus.catalog import converters, extractors, transforms
from locus.image import ResolvedImage

CATALOG: dict[str, Callable[[], ResolvedImage]] = {
    # Tier 1 — document -> structured (root images)
    "doc-to-tables": extractors.doc_to_tables,
    "invoice-extractor": extractors.invoice_extractor,
    "receipt-extractor": extractors.receipt_extractor,
    "bank-statement-extractor": extractors.bank_statement_extractor,
    "report-extractor": extractors.report_extractor,
    # Tier 2 — format conversion (table -> table, sets preferred export)
    "any-to-json": converters.any_to_json,
    "any-to-csv": converters.any_to_csv,
    "any-to-markdown": converters.any_to_markdown,
    # Tier 3 — cleaning, quality, identity (table -> table)
    "data-cleaner": transforms.data_cleaner,
    "deduplicator": transforms.deduplicator,
    "normalizer": transforms.normalizer,
    "column-mapper": transforms.column_mapper,
    # Tier 6 — unique / trust (table -> table)
    "pii-redactor": transforms.pii_redactor,
    "drop-flagged": transforms.drop_flagged,
    "anomaly-flagger": transforms.anomaly_flagger,
    "data-profiler": transforms.data_profiler,
}


def resolve_catalog(ref: str) -> ResolvedImage | None:
    name = ref.split(":", 1)[0]
    factory = CATALOG.get(name)
    return factory() if factory else None


def all_images() -> list[ResolvedImage]:
    return [factory() for factory in CATALOG.values()]


__all__ = ["CATALOG", "resolve_catalog", "all_images"]
