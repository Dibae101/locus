"""Typed error hierarchy for the Locus runtime (Layer 2).

Mirrors the engine's split into fail-fast (plan/config) and recoverable classes.
Distinct from ``locus_engine.errors`` so callers can tell runtime concerns from
engine concerns.
"""

from __future__ import annotations


class LocusRuntimeError(Exception):
    """Base class for all Locus runtime (Layer 2) errors."""


class ConfigError(LocusRuntimeError):
    """Invalid Locusfile or run configuration. Fail-fast (Req 3.7)."""


class CredentialError(LocusRuntimeError):
    """A credential-safety violation (raw key in file, tracked .env) (Req 4.3, 4.5)."""


class PlanError(LocusRuntimeError):
    """A pipeline cannot be planned (cycle, type mismatch). Fail-fast (Req 5.6, 6.5)."""


class CycleError(PlanError):
    """The pipeline graph contains a cycle (Req 5.6)."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = list(cycle)
        super().__init__(f"pipeline graph contains a cycle: {' -> '.join(self.cycle)}")


class TypeMismatchError(PlanError):
    """Two adjacent stages have incompatible artifact types (Req 6.5)."""

    def __init__(self, producer: str, consumer: str, emitted: str, accepted: list[str]) -> None:
        self.producer = producer
        self.consumer = consumer
        self.emitted = emitted
        self.accepted = accepted
        super().__init__(
            f"stage {consumer!r} accepts {accepted} but {producer!r} emits {emitted!r}"
        )


class ConformanceError(PlanError):
    """A non-conformant stage in strict mode (Req 7.7)."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"stage {stage!r} is not provenance-conformant (strict mode)")


class ImageNotFoundError(LocusRuntimeError):
    """A referenced image cannot be found in the registry (Req 2.4)."""

    def __init__(self, ref: str) -> None:
        self.ref = ref
        super().__init__(f"image not found: {ref!r}")


class BackendUnavailableError(LocusRuntimeError):
    """The selected runtime backend is unavailable (Req 1.5)."""

    def __init__(self, backend: str) -> None:
        self.backend = backend
        super().__init__(f"runtime backend {backend!r} is unavailable")
