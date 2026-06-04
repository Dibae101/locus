"""Typed error hierarchy for the Locus engine.

Errors split into two operational classes (see design.md "Error Handling"):

- **Per-source, recoverable:** recorded against a source id; the run continues.
- **Run-fatal, fail-fast:** raised before/at run start; no further sources processed.

All engine errors derive from :class:`LocusError` so callers can catch broadly.
"""

from __future__ import annotations


class LocusError(Exception):
    """Base class for all Locus engine errors."""


class ConfigError(LocusError):
    """Invalid pipeline configuration. Run-fatal, fail-fast (Req 12.3, 12.4)."""


class RegistrationError(LocusError):
    """A plugin failed registration validation (Req 10.4)."""

    def __init__(self, plugin_name: str, missing_methods: list[str]) -> None:
        self.plugin_name = plugin_name
        self.missing_methods = list(missing_methods)
        joined = ", ".join(self.missing_methods)
        super().__init__(
            f"plugin {plugin_name!r} is missing required method(s): {joined}"
        )


class SourceError(LocusError):
    """Base for per-source, recoverable errors. Carries the offending source id."""

    def __init__(self, source_id: str, reason: str) -> None:
        self.source_id = source_id
        self.reason = reason
        super().__init__(f"[{source_id}] {reason}")


class ConnectorError(SourceError):
    """A connector could not read a source (Req 1.5)."""


class UnsupportedSourceError(SourceError):
    """No connector declares support for a submitted source (Req 1.4)."""


class ParserError(SourceError):
    """A parser failed to process a source (Req 3.5)."""


class RoutingError(SourceError):
    """The parser router could not determine/serve a content type (Req 2.5, 2.6)."""


class ParserUnavailableError(LocusError):
    """A configured parser is unavailable at runtime. Run-fatal (Req 2.4)."""

    def __init__(self, parser_name: str) -> None:
        self.parser_name = parser_name
        super().__init__(f"configured parser {parser_name!r} is unavailable")


class ExtractionError(SourceError):
    """Extraction or schema validation failed for a source (Req 4.6)."""


class EmitError(LocusError):
    """The emitter could not write output (Req 8.7)."""

    def __init__(self, destination: str, reason: str) -> None:
        self.destination = destination
        self.reason = reason
        super().__init__(f"failed writing to {destination!r}: {reason}")
