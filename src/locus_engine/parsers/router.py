"""Parser router (Stage 3.2).

Selects a registered parser for a source's content type, honoring a configured
override and the error semantics in Req 2. The router delegates registration/lookup
to the ``PluginRegistry`` and translates lookup failures into the precise routing
errors the pipeline expects.

Requirements: 2.1, 2.3, 2.4, 2.5, 2.6.
"""

from __future__ import annotations

from locus_engine.errors import ParserUnavailableError, RoutingError
from locus_engine.plugins import Parser, RawSource
from locus_engine.registry import PluginRegistry


class ParserRouter:
    """Routes a RawSource to the appropriate parser."""

    def __init__(self, registry: PluginRegistry, overrides: dict[str, str] | None = None):
        self._registry = registry
        self._overrides = overrides or {}

    def route(self, raw: RawSource) -> Parser:
        content_type = raw.content_type
        if not content_type or content_type == "application/octet-stream":
            raise RoutingError(raw.source_id, "could not determine content type")

        override = self._overrides.get(content_type)
        try:
            return self._registry.parser_for(content_type, override=override)
        except LookupError as exc:
            if override is not None:
                # A configured parser that is not registered is run-fatal (Req 2.4).
                raise ParserUnavailableError(override) from exc
            # No parser supports this content type: per-source skip (Req 2.6).
            raise RoutingError(
                raw.source_id, f"no parser for content type {content_type!r}"
            ) from exc
