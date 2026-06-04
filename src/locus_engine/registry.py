"""Plugin registry with registration validation (Stage 2.2).

Validates that a plugin implements its interface's required methods before
registering it (Req 10.3); rejects incomplete plugins with an explicit
missing-method list (Req 10.4). A config-named component overrides a built-in that
declares support for the same type (Req 10.5).

Requirements: 10.2, 10.3, 10.4, 10.5.
"""

from __future__ import annotations

from locus_engine.errors import RegistrationError
from locus_engine.plugins import (
    REQUIRED_METHODS,
    Connector,
    Emitter,
    ExtractionEngine,
    Parser,
    SourceRef,
    Validator,
)


class PluginRegistry:
    """Holds registered plugins by kind and resolves the component to use."""

    def __init__(self) -> None:
        self._by_kind: dict[type, dict[str, object]] = {
            Connector: {},
            Parser: {},
            ExtractionEngine: {},
            Validator: {},
            Emitter: {},
        }

    # --- registration -----------------------------------------------------

    def register(self, plugin: object, kind: type) -> None:
        """Validate then register a plugin under the given interface ``kind``."""
        if kind not in REQUIRED_METHODS:
            raise RegistrationError(type(plugin).__name__, [f"<unknown kind {kind!r}>"])

        missing = self._missing_methods(plugin, kind)
        if missing:
            raise RegistrationError(type(plugin).__name__, missing)

        name = getattr(plugin, "name", None)
        if not name:
            raise RegistrationError(type(plugin).__name__, ["name"])

        self._by_kind[kind][name] = plugin

    @staticmethod
    def _missing_methods(plugin: object, kind: type) -> list[str]:
        missing: list[str] = []
        for method in REQUIRED_METHODS[kind]:
            attr = getattr(plugin, method, None)
            if attr is None or not callable(attr):
                missing.append(method)
        return missing

    # --- resolution -------------------------------------------------------

    def get(self, kind: type, name: str) -> object | None:
        return self._by_kind[kind].get(name)

    def names(self, kind: type) -> list[str]:
        return list(self._by_kind[kind])

    def connector_for(self, ref: SourceRef) -> Connector:
        """First registered connector that declares support for the ref."""
        for plugin in self._by_kind[Connector].values():
            if isinstance(plugin, Connector) and plugin.supports(ref):
                return plugin
        raise LookupError(f"no connector supports {ref.uri!r}")

    def parser_for(self, content_type: str, override: str | None = None) -> Parser:
        """Resolve a parser, honoring a config override name (Req 2.3, 10.5)."""
        parsers = self._by_kind[Parser]
        if override is not None:
            chosen = parsers.get(override)
            if chosen is None or not isinstance(chosen, Parser):
                raise LookupError(f"configured parser {override!r} is not registered")
            return chosen
        for plugin in parsers.values():
            if isinstance(plugin, Parser) and plugin.supports(content_type):
                return plugin
        raise LookupError(f"no parser supports content type {content_type!r}")
