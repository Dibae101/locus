"""Tier 2 converter images: table -> table, declaring a preferred export format.

Conversion is a property of how the final table is emitted. These images pass the
table through unchanged (preserving lineage) and record a preferred output format in
the stage config side-channel, which the exporter/serving layer can honor.
"""

from __future__ import annotations

import pandas as pd

from locus.catalog.common import transform_image
from locus.image import ResolvedImage, StageContext


def _passthrough_with_format(fmt: str) -> type:
    class _Cap:
        def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
            if not inputs:
                raise ValueError("converter requires one upstream table input")
            ctx.config["_preferred_format"] = fmt
            return inputs[0], "deterministic"

    return _Cap


def any_to_json() -> ResolvedImage:
    return transform_image(
        "any-to-json", "Emit the table as clean JSON.", _passthrough_with_format("json")
    )


def any_to_csv() -> ResolvedImage:
    return transform_image(
        "any-to-csv", "Emit the table as CSV.", _passthrough_with_format("csv")
    )


def any_to_markdown() -> ResolvedImage:
    return transform_image(
        "any-to-markdown", "Emit the table as Markdown.", _passthrough_with_format("markdown")
    )
