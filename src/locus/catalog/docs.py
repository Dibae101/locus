"""Per-image documentation for the catalog.

Maps each image name to richer docs the Hub renders on its detail page: a longer
description, example use cases, and a ready-to-copy Locusfile snippet. Keeping this
separate from the capability code lets the Hub show Docker-Hub-style pages without
bloating the runtime modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImageDoc:
    summary: str
    details: str
    examples: list[str] = field(default_factory=list)
    tier: str = ""


def _locusfile(image: str, *, pipeline: bool = False) -> str:
    if pipeline:
        return (
            "source:\n"
            "  type: files\n"
            "  path: ./data/input.csv\n"
            "pipeline:\n"
            "  - id: extract\n"
            "    image: doc-to-tables\n"
            f"  - id: step\n"
            f"    image: {image}\n"
            "    needs: [extract]\n"
        )
    return (
        f"image: {image}\n"
        "source:\n"
        "  type: files\n"
        "  path: ./data/input.csv\n"
    )


DOCS: dict[str, ImageDoc] = {
    "doc-to-tables": ImageDoc(
        summary="Extract tables from documents into validated, source-grounded rows.",
        details=(
            "The general-purpose extractor and the best starting point. It ingests a "
            "source (CSV, PDF text, HTML, or structured records), detects tabular "
            "structure, and emits clean rows where every cell carries its source "
            "location and a faithfulness score. Runs fully locally by default; supply "
            "an LLM key to enable fuzzy field mapping."
        ),
        examples=["Invoices, reports, exported spreadsheets, scraped HTML tables."],
        tier="Document → Structured",
    ),
    "invoice-extractor": ImageDoc(
        summary="Extract invoice fields and line items.",
        details=(
            "A doc-to-tables specialization tuned for invoices: vendor, totals, dates, "
            "and per-row line items. Output is grounded so each value traces back to "
            "the source document."
        ),
        examples=["Accounts-payable automation, expense pipelines."],
        tier="Document → Structured",
    ),
    "receipt-extractor": ImageDoc(
        summary="Extract receipts into expense records.",
        details="Turns receipts into structured expense rows with provenance.",
        examples=["Expense reporting, reimbursement workflows."],
        tier="Document → Structured",
    ),
    "bank-statement-extractor": ImageDoc(
        summary="Extract bank statements into transaction tables.",
        details="Parses statements into per-transaction rows (date, description, amount).",
        examples=["Reconciliation, cash-flow analysis."],
        tier="Document → Structured",
    ),
    "report-extractor": ImageDoc(
        summary="Extract tables and KPIs from reports.",
        details="Pulls tabular data and key figures out of annual or analytical reports.",
        examples=["Financial reports, research summaries."],
        tier="Document → Structured",
    ),
    "any-to-json": ImageDoc(
        summary="Emit the table as clean JSON.",
        details="A converter stage that marks the result for JSON output. Compose it "
        "after an extractor to get JSON instead of a table.",
        examples=["Feeding an API or an LLM that expects JSON."],
        tier="Conversion",
    ),
    "any-to-csv": ImageDoc(
        summary="Emit the table as CSV.",
        details="Converter stage that marks the result for CSV output.",
        examples=["Spreadsheet hand-off, analytics ingestion."],
        tier="Conversion",
    ),
    "any-to-markdown": ImageDoc(
        summary="Emit the table as Markdown.",
        details="Converter stage that marks the result for Markdown output.",
        examples=["Docs, reports, LLM prompts."],
        tier="Conversion",
    ),
    "data-cleaner": ImageDoc(
        summary="Trim and normalize cell whitespace.",
        details="Cleans extracted values (whitespace, stray characters) while preserving "
        "each cell's provenance.",
        examples=["Post-extraction cleanup before analysis."],
        tier="Cleaning & Quality",
    ),
    "deduplicator": ImageDoc(
        summary="Remove duplicate rows by key columns.",
        details="Drops duplicate rows matched on configurable key columns. Configure "
        "`config.keys` on the stage.",
        examples=["De-duping merged datasets, entity lists."],
        tier="Cleaning & Quality",
    ),
    "normalizer": ImageDoc(
        summary="Normalize text columns (case + whitespace).",
        details="Lowercases and collapses whitespace on chosen text columns "
        "(`config.columns`).",
        examples=["Standardizing names/codes before joins."],
        tier="Cleaning & Quality",
    ),
    "column-mapper": ImageDoc(
        summary="Rename or select output columns.",
        details="Renames columns via `config.rename`; lineage keys follow the rename.",
        examples=["Mapping extracted columns to a target schema."],
        tier="Cleaning & Quality",
    ),
    "pii-redactor": ImageDoc(
        summary="Mask emails, phones, and SSNs while preserving grounding.",
        details="Redacts common PII patterns. Follows mask semantics: the value is "
        "hidden but its grounding/faithfulness is preserved, so you keep an auditable "
        "trail without exposing the secret.",
        examples=["Privacy-safe sharing, compliance pipelines."],
        tier="Trust & Privacy",
    ),
    "drop-flagged": ImageDoc(
        summary="Drop rows flagged as low-confidence.",
        details="Removes rows the grounding contract flagged below the threshold, so "
        "only trustworthy rows pass downstream.",
        examples=["Quality gate before loading into a warehouse."],
        tier="Trust & Privacy",
    ),
    "anomaly-flagger": ImageDoc(
        summary="Flag numeric outlier rows (robust MAD).",
        details="Flags rows whose numeric values are statistical outliers using the "
        "median absolute deviation method (robust to small samples).",
        examples=["Fraud signals, data-quality review."],
        tier="Trust & Privacy",
    ),
    "data-profiler": ImageDoc(
        summary="Profile the table (row/column stats); passthrough.",
        details="Computes row/column statistics (non-null counts, cardinality) without "
        "changing the data.",
        examples=["Understanding a dataset before processing."],
        tier="Trust & Privacy",
    ),
}

_DEFAULT = ImageDoc(summary="", details="No extended documentation available.", tier="")


def get_doc(name: str) -> ImageDoc:
    return DOCS.get(name, _DEFAULT)


def example_locusfile(name: str) -> str:
    """A ready-to-copy Locusfile for this image (pipeline form for transforms)."""
    transforms = {
        "data-cleaner", "deduplicator", "normalizer", "column-mapper",
        "pii-redactor", "drop-flagged", "anomaly-flagger", "data-profiler",
        "any-to-json", "any-to-csv", "any-to-markdown",
    }
    return _locusfile(name, pipeline=name in transforms)
