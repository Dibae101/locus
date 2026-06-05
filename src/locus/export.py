"""Result export (Layer 2).

Turns a result DataFrame into a file in a chosen format. The format can be declared
in the Locusfile (``export.format`` / ``export.path``) or inferred from the output
path's extension, and the CLI ``--export`` flag overrides the Locusfile path.

Supported formats: ``csv``, ``parquet``, ``json``, ``markdown``. Markdown is written
without a third-party dependency so the core stays lightweight.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from locus.errors import ConfigError

# Map of file extension -> canonical format name.
_EXT_FORMAT: dict[str, str] = {
    ".csv": "csv",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
}

SUPPORTED_FORMATS: tuple[str, ...] = ("csv", "parquet", "json", "markdown")


def infer_format(path: str) -> str | None:
    """Infer the export format from a path's extension, or None if unknown."""
    return _EXT_FORMAT.get(Path(path).suffix.lower())


def resolve_format(path: str, declared: str | None) -> str:
    """Resolve the final format: an explicit declaration wins, else infer from the
    path extension, else default to CSV. Raises on an unsupported declaration."""
    if declared:
        fmt = declared.strip().lower()
        if fmt not in SUPPORTED_FORMATS:
            raise ConfigError(
                f"unsupported export format {declared!r}; "
                f"choose one of: {', '.join(SUPPORTED_FORMATS)}"
            )
        return fmt
    return infer_format(path) or "csv"


def write_export(
    frame: pd.DataFrame, path: str, fmt: str, *, include_lineage: bool = True
) -> None:
    """Write ``frame`` to ``path`` in the given format.

    When ``include_lineage`` is False the per-cell ``_lineage`` provenance column is
    dropped so the output is a clean, human-facing table.
    """
    frame = _maybe_drop_lineage(frame, include_lineage)
    target = Path(path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        frame.to_csv(target, index=False)
    elif fmt == "parquet":
        frame.to_parquet(target, index=False)
    elif fmt == "json":
        target.write_text(frame.to_json(orient="records", indent=2) or "[]")
    elif fmt == "markdown":
        target.write_text(_to_markdown(frame))
    else:  # pragma: no cover - guarded by resolve_format
        raise ConfigError(f"unsupported export format {fmt!r}")


def _maybe_drop_lineage(frame: pd.DataFrame, include_lineage: bool) -> pd.DataFrame:
    """Drop the per-cell ``_lineage`` provenance column when not wanted."""
    from locus.emit_constants import LINEAGE_COLUMN

    if not include_lineage and LINEAGE_COLUMN in frame.columns:
        return frame.drop(columns=[LINEAGE_COLUMN])
    return frame


def _to_markdown(frame: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavored Markdown table without requiring the
    optional ``tabulate`` dependency."""
    columns = [str(c) for c in frame.columns]
    if not columns:
        return "\n"
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, divider]
    for _, row in frame.iterrows():
        cells = [_md_cell(row[col]) for col in frame.columns]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _md_cell(value: object) -> str:
    text = "" if value is None else str(value)
    # Escape pipes and collapse newlines so the table stays well-formed.
    return text.replace("|", "\\|").replace("\n", " ").strip()
