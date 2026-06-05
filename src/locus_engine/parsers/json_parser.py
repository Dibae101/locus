"""JSON file parser (dependency-free).

Turns a JSON document on disk into an IR table:

- A top-level array of objects becomes one row per object (union of keys as columns).
- A single object becomes a two-column ``key | value`` table, with nested objects and
  arrays flattened using dotted / indexed key paths.

Nested scalars are flattened so deeply-structured config files (e.g. a browser
extension ``manifest.json``) still present as a readable table. The structured-records
path (API/DB connectors, ``raw.records``) is handled by ``RecordsParser``; this parser
covers JSON arriving as file bytes.

Requirements: 2.2, 3.1, 3.2, 3.3.
"""

from __future__ import annotations

import json
from typing import Any

from locus_engine.errors import ParserError
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.plugins import RawSource
from locus_engine.provenance import SourceLocation


class JsonParser:
    """Parses a JSON file (bytes) into an IR table."""

    name = "json"
    content_types: tuple[str, ...] = ("application/json",)

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        # When a connector already produced structured records (API/DB), build the
        # table directly from them; otherwise parse the JSON file bytes.
        if raw.records is not None:
            payload: Any = raw.records
        elif raw.data is not None:
            try:
                payload = json.loads(raw.data.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ParserError(raw.source_id, f"json parse failed: {exc}") from exc
        else:
            raise ParserError(raw.source_id, "json parser requires raw bytes or records")

        grid, note = self._to_grid(payload)
        if not grid:
            raise ParserError(raw.source_id, "no tabular content in json")
        loc = SourceLocation(source_id=raw.source_id, index=0, note=note)
        element = IRElement(
            kind=IRElementKind.TABLE, table=IRTable(cells=grid, location=loc), location=loc
        )
        return IntermediateRepresentation(
            source_id=raw.source_id, content_type=raw.content_type, elements=[element]
        )

    def _to_grid(self, payload: Any) -> tuple[list[list[str]], str]:
        # Array of objects -> one row per object.
        if isinstance(payload, list) and payload and all(isinstance(x, dict) for x in payload):
            flat_rows = [self._flatten(obj) for obj in payload]
            columns: list[str] = []
            for row in flat_rows:
                for key in row:
                    if key not in columns:
                        columns.append(key)
            grid = [columns]
            for row in flat_rows:
                grid.append([self._cell(row.get(c)) for c in columns])
            return grid, "json records"

        # Single object -> key/value table (flattened).
        if isinstance(payload, dict):
            flat_obj = self._flatten(payload)
            grid = [["key", "value"]]
            for key, value in flat_obj.items():
                grid.append([key, self._cell(value)])
            return grid, "json object"

        # Array of scalars -> single-column table.
        if isinstance(payload, list) and payload:
            grid = [["value"]]
            for item in payload:
                grid.append([self._cell(item)])
            return grid, "json array"

        return [], "json"

    def _flatten(self, obj: Any, prefix: str = "") -> dict[str, Any]:
        """Flatten nested dicts/lists into dotted/indexed key paths."""
        out: dict[str, Any] = {}
        if isinstance(obj, dict):
            for key, value in obj.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                out.update(self._flatten(value, path))
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                path = f"{prefix}[{i}]"
                out.update(self._flatten(value, path))
        else:
            out[prefix] = obj
        return out

    @staticmethod
    def _cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
