"""Tier 1 extractor images: source -> grounded table.

These wrap the Layer 1 engine pipeline. ``doc-to-tables`` is the general reference;
the others are specializations that carry a domain description (and, where useful, a
hint schema) but share the same engine path so they are cheap to provide.
"""

from __future__ import annotations

import pandas as pd

from locus.catalog.common import manifest, table_type
from locus.image import ResolvedImage, StageContext
from locus.manifest import ImageManifest
from locus_engine.config import PipelineConfig
from locus_engine.connectors.files import FileConnector
from locus_engine.parsers.archive import ArchiveParser
from locus_engine.parsers.csv_parser import CsvParser
from locus_engine.parsers.html import HtmlParser
from locus_engine.parsers.image import ImageParser
from locus_engine.parsers.json_parser import JsonParser
from locus_engine.parsers.markdown import MarkdownParser
from locus_engine.parsers.office import (
    DocxParser,
    EpubParser,
    OdtParser,
    PptxParser,
    XlsxParser,
)
from locus_engine.parsers.records import RecordsParser
from locus_engine.parsers.text import TextParser
from locus_engine.pipeline import Pipeline
from locus_engine.plugins import Connector, Parser, SourceRef
from locus_engine.registry import PluginRegistry


def _engine_registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register(FileConnector(), Connector)
    reg.register(CsvParser(), Parser)
    reg.register(HtmlParser(), Parser)
    reg.register(JsonParser(), Parser)
    reg.register(RecordsParser(), Parser)
    reg.register(MarkdownParser(), Parser)
    reg.register(TextParser(), Parser)
    reg.register(DocxParser(), Parser)
    reg.register(PptxParser(), Parser)
    reg.register(XlsxParser(), Parser)
    reg.register(OdtParser(), Parser)
    reg.register(EpubParser(), Parser)
    reg.register(ArchiveParser(), Parser)
    reg.register(ImageParser(), Parser)
    try:
        from locus_engine.parsers.pdf import PdfParser

        reg.register(PdfParser(), Parser)
    except Exception:  # pragma: no cover - optional dep
        pass
    return reg


class _EngineCapability:
    """Runs the engine over a file source and returns a grounded table."""

    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        source = ctx.source
        if source is None or source.path is None:
            raise ValueError("extractor requires a file source with a path")
        cfg = PipelineConfig.load(
            {
                "source": {"type": "files", "path": source.path},
                "grounding_threshold": ctx.grounding_threshold,
            }
        )
        pipeline = Pipeline(cfg, _engine_registry())
        out = pipeline.run([SourceRef(uri=source.path, kind="file")])
        return pipeline.emit(out), out.table.produced_by_engine


def _extractor(name: str, description: str) -> ResolvedImage:
    m: ImageManifest = manifest(
        name, description=description, accepts=[], emits=table_type()
    )
    return ResolvedImage(manifest=m, capability=_EngineCapability())


def doc_to_tables() -> ResolvedImage:
    return _extractor("doc-to-tables", "Extract tables from documents into validated rows.")


def invoice_extractor() -> ResolvedImage:
    return _extractor("invoice-extractor", "Extract invoice fields and line items.")


def receipt_extractor() -> ResolvedImage:
    return _extractor("receipt-extractor", "Extract receipts into expense records.")


def bank_statement_extractor() -> ResolvedImage:
    return _extractor(
        "bank-statement-extractor", "Extract bank statements into transaction tables."
    )


def report_extractor() -> ResolvedImage:
    return _extractor("report-extractor", "Extract tables and KPIs from reports.")
