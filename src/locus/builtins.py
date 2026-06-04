"""Built-in capability images (Layer 2, Stage 3.1).

These wrap the Layer 1 engine as runnable capabilities. ``doc_to_tables`` is the
reference image: it runs the engine pipeline (connector -> parser -> extract ->
clean -> ground -> emit) over a source and returns a DataFrame with the ``_lineage``
column. It is the first catalog image and the runtime's integration point with the
engine.
"""

from __future__ import annotations

import pandas as pd

from locus.artifacts import ArtifactKind, ArtifactType
from locus.image import ResolvedImage, StageContext, _builtin_manifest
from locus.manifest import ImageManifest
from locus_engine.config import PipelineConfig
from locus_engine.connectors.files import FileConnector
from locus_engine.parsers.csv_parser import CsvParser
from locus_engine.parsers.router import ParserRouter  # noqa: F401 (used indirectly)
from locus_engine.pipeline import Pipeline
from locus_engine.plugins import Connector, Parser
from locus_engine.registry import PluginRegistry


def _engine_registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register(FileConnector(), Connector)
    reg.register(CsvParser(), Parser)
    # Optional parsers are registered when their extras are installed.
    try:
        from locus_engine.parsers.pdf import PdfParser

        reg.register(PdfParser(), Parser)
    except Exception:  # pragma: no cover - optional dep
        pass
    from locus_engine.parsers.html import HtmlParser
    from locus_engine.parsers.records import RecordsParser

    reg.register(HtmlParser(), Parser)
    reg.register(RecordsParser(), Parser)
    return reg


class DocToTablesCapability:
    """Runs the engine over a file source and returns a grounded table."""

    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        from locus_engine.plugins import SourceRef

        source = ctx.source
        if source is None or source.path is None:
            raise ValueError("doc-to-tables requires a file source with a path")

        cfg = PipelineConfig.load(
            {
                "source": {"type": "files", "path": source.path},
                "grounding_threshold": ctx.grounding_threshold,
            }
        )
        pipeline = Pipeline(cfg, _engine_registry())
        ref = SourceRef(uri=source.path, kind="file")
        out = pipeline.run([ref])
        frame = pipeline.emit(out)
        return frame, out.table.produced_by_engine


def doc_to_tables() -> ResolvedImage:
    manifest: ImageManifest = _builtin_manifest(
        "doc-to-tables",
        accepts=[],  # root capability: reads a source, not an upstream artifact
        emits=ArtifactType(kind=ArtifactKind.TABLE),
    )
    return ResolvedImage(manifest=manifest, capability=DocToTablesCapability())


class DropFlaggedCapability:
    """Accepts a table artifact and emits the same table with flagged rows removed.

    A minimal table->table composition stage: it reads the upstream frame and drops
    rows whose ``_lineage._row_flagged`` is true, demonstrating multi-stage chaining
    with a stable table contract.
    """

    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        if not inputs:
            raise ValueError("drop-flagged requires one upstream table input")
        frame = inputs[0]
        if "_lineage" in frame.columns:
            keep = frame["_lineage"].apply(
                lambda lin: not (isinstance(lin, dict) and lin.get("_row_flagged"))
            )
            frame = frame[keep].reset_index(drop=True)
        return frame, "deterministic"


def drop_flagged() -> ResolvedImage:
    table = ArtifactType(kind=ArtifactKind.TABLE)
    manifest = _builtin_manifest("drop-flagged", accepts=[table], emits=table)
    return ResolvedImage(manifest=manifest, capability=DropFlaggedCapability())


class StripLineageCapability:
    """A deliberately NON-conformant table->table stage that drops the lineage
    column. Used to exercise permissive-mode lineage-breaking and strict-mode
    plan-time rejection."""

    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        if not inputs:
            raise ValueError("strip-lineage requires one upstream table input")
        frame = inputs[0]
        return frame.drop(columns=["_lineage"], errors="ignore"), "deterministic"


def strip_lineage() -> ResolvedImage:
    table = ArtifactType(kind=ArtifactKind.TABLE)
    manifest = _builtin_manifest("strip-lineage", accepts=[table], emits=table)
    manifest.provenance_conformant = False  # explicitly non-conformant
    return ResolvedImage(manifest=manifest, capability=StripLineageCapability())


# Registry of built-in images by name (used until OCI pull lands in Stage 6).
BUILTIN_IMAGES = {
    "doc-to-tables": doc_to_tables,
    "drop-flagged": drop_flagged,
    "strip-lineage": strip_lineage,
}


def resolve_builtin(ref: str) -> ResolvedImage | None:
    name = ref.split(":", 1)[0]
    factory = BUILTIN_IMAGES.get(name)
    return factory() if factory else None
