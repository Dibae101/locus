"""Table -> table transform images (cleaning, identity, trust).

Each capability operates on the result frame and preserves the per-cell ``_lineage``
column so provenance survives composition. PII redaction follows the engine's
mask semantics: the value is hidden but its grounding is preserved.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from locus.catalog.common import data_columns, transform_image
from locus.emit_constants import LINEAGE_COLUMN
from locus.image import ResolvedImage, StageContext


def _require_input(inputs: list[pd.DataFrame], name: str) -> pd.DataFrame:
    if not inputs:
        raise ValueError(f"{name} requires one upstream table input")
    return inputs[0]


# --- drop-flagged ---------------------------------------------------------


class _DropFlagged:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        frame = _require_input(inputs, "drop-flagged")
        if LINEAGE_COLUMN in frame.columns:
            keep = frame[LINEAGE_COLUMN].apply(
                lambda lin: not (isinstance(lin, dict) and lin.get("_row_flagged"))
            )
            frame = frame[keep].reset_index(drop=True)
        return frame, "deterministic"


def drop_flagged() -> ResolvedImage:
    return transform_image("drop-flagged", "Drop rows flagged as low-confidence.", _DropFlagged)


# --- data-cleaner (strip whitespace, drop fully-empty rows) ---------------


class _DataCleaner:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        frame = _require_input(inputs, "data-cleaner").copy()
        for col in data_columns(frame):
            frame[col] = frame[col].apply(lambda v: v.strip() if isinstance(v, str) else v)
        return frame, "deterministic"


def data_cleaner() -> ResolvedImage:
    return transform_image("data-cleaner", "Trim and normalize cell whitespace.", _DataCleaner)


# --- normalizer (lowercase + collapse spaces on text columns) -------------


class _Normalizer:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        frame = _require_input(inputs, "normalizer").copy()
        cols = ctx.config.get("columns") or data_columns(frame)
        for col in cols:
            if col in frame.columns:
                frame[col] = frame[col].apply(
                    lambda v: re.sub(r"\s+", " ", v.strip().lower()) if isinstance(v, str) else v
                )
        return frame, "deterministic"


def normalizer() -> ResolvedImage:
    return transform_image("normalizer", "Normalize text columns (case + whitespace).", _Normalizer)


# --- deduplicator (exact match on key columns) ----------------------------


class _Deduplicator:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        frame = _require_input(inputs, "deduplicator")
        keys = ctx.config.get("keys") or data_columns(frame)
        keys = [k for k in keys if k in frame.columns]
        if not keys:
            return frame, "deterministic"
        deduped = frame.drop_duplicates(subset=keys).reset_index(drop=True)
        return deduped, "deterministic"


def deduplicator() -> ResolvedImage:
    return transform_image("deduplicator", "Remove duplicate rows by key columns.", _Deduplicator)


# --- column-mapper (rename / select columns) ------------------------------


class _ColumnMapper:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        frame = _require_input(inputs, "column-mapper").copy()
        rename: dict[str, str] = ctx.config.get("rename", {})
        if rename:
            frame = frame.rename(columns=rename)
            # keep lineage keys aligned with renamed columns
            if LINEAGE_COLUMN in frame.columns:
                frame[LINEAGE_COLUMN] = frame[LINEAGE_COLUMN].apply(
                    lambda lin: _rename_lineage(lin, rename) if isinstance(lin, dict) else lin
                )
        return frame, "deterministic"


def _rename_lineage(lineage: dict[str, Any], rename: dict[str, str]) -> dict[str, Any]:
    out = {k: v for k, v in lineage.items() if k.startswith("_")}
    for k, v in lineage.items():
        if k.startswith("_"):
            continue
        out[rename.get(k, k)] = v
    return out


def column_mapper() -> ResolvedImage:
    return transform_image("column-mapper", "Rename or select output columns.", _ColumnMapper)


# --- pii-redactor (mask emails / phones / SSNs; preserve grounding) -------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\b(?:\+?\d{1,2}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)\d{3}[\s-]?\d{4}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def _redact(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    v = _EMAIL.sub("[EMAIL]", value)
    v = _SSN.sub("[SSN]", v)
    v = _PHONE.sub("[PHONE]", v)
    return v


class _PiiRedactor:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        frame = _require_input(inputs, "pii-redactor").copy()
        for col in data_columns(frame):
            frame[col] = frame[col].apply(_redact)
        # mask semantics: value hidden, grounding preserved (no lineage change)
        return frame, "deterministic"


def pii_redactor() -> ResolvedImage:
    return transform_image(
        "pii-redactor", "Mask emails, phones, and SSNs while preserving grounding.", _PiiRedactor
    )


# --- anomaly-flagger (flag rows that are statistical outliers) ------------


class _AnomalyFlagger:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        frame = _require_input(inputs, "anomaly-flagger").copy()
        if LINEAGE_COLUMN not in frame.columns:
            return frame, "deterministic"
        numeric_cols = [
            c for c in data_columns(frame) if pd.api.types.is_numeric_dtype(frame[c])
        ]
        flags = [False] * len(frame)
        for col in numeric_cols:
            series = pd.to_numeric(frame[col], errors="coerce")
            median = series.median()
            mad = (series - median).abs().median()
            if mad and not pd.isna(mad):
                # 0.6745 scales MAD to a std-equivalent; flag |z| > 3.5.
                modified_z = 0.6745 * (series - median).abs() / mad
                outliers = modified_z > 3.5
            else:
                # MAD is 0 (most values identical): flag anything that deviates from
                # the dominant value by more than a small tolerance.
                spread = (series - median).abs()
                tol = max(spread.median(), 1e-9)
                outliers = spread > tol * 1.0
            flags = [a or bool(b) for a, b in zip(flags, outliers, strict=True)]
        new_lineage = []
        for i, lin in enumerate(frame[LINEAGE_COLUMN]):
            lin = dict(lin) if isinstance(lin, dict) else {}
            if flags[i]:
                lin["_row_flagged"] = True
                lin["_anomaly"] = True
            new_lineage.append(lin)
        frame[LINEAGE_COLUMN] = pd.Series(new_lineage, index=frame.index, dtype=object)
        return frame, "deterministic"


def anomaly_flagger() -> ResolvedImage:
    return transform_image(
        "anomaly-flagger", "Flag numeric outlier rows (robust MAD).", _AnomalyFlagger
    )


# --- data-profiler (passthrough; emits a profile in config side-channel) --


class _DataProfiler:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        frame = _require_input(inputs, "data-profiler")
        # Non-destructive: returns the frame unchanged. A profile is computed and
        # stored on ctx.config for callers/serving to read.
        profile: dict[str, Any] = {"rows": len(frame), "columns": {}}
        for col in data_columns(frame):
            series = frame[col]
            profile["columns"][col] = {
                "non_null": int(series.notna().sum()),
                "unique": int(series.nunique()),
            }
        ctx.config["_profile"] = profile
        return frame, "deterministic"


def data_profiler() -> ResolvedImage:
    return transform_image(
        "data-profiler", "Profile the table (row/column stats); passthrough.", _DataProfiler
    )
