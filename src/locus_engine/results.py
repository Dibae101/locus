"""Run result and per-source outcome records.

A :class:`RunResult` aggregates per-source outcomes and determines the
corpus-level success: a corpus with at least one successful source reports
success even when individual sources recorded errors (Req 11.5).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Outcome(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class SourceOutcome(BaseModel):
    """The recorded result of processing a single source."""

    source_id: str
    outcome: Outcome
    phase: str | None = None  # phase at which an error/skip occurred, if any
    reason: str | None = None


class RunResult(BaseModel):
    """Aggregate outcome of a corpus run."""

    source_outcomes: list[SourceOutcome] = Field(default_factory=list)
    rows_emitted: int = 0
    rows_flagged: int = 0
    rows_rejected: int = 0

    def record(self, outcome: SourceOutcome) -> None:
        self.source_outcomes.append(outcome)

    @property
    def sources_processed(self) -> int:
        return len(self.source_outcomes)

    @property
    def succeeded(self) -> list[SourceOutcome]:
        return [o for o in self.source_outcomes if o.outcome is Outcome.SUCCESS]

    @property
    def errored(self) -> list[SourceOutcome]:
        return [o for o in self.source_outcomes if o.outcome is Outcome.ERROR]

    @property
    def corpus_success(self) -> bool:
        """True if at least one source processed successfully (Req 11.5)."""
        return any(o.outcome is Outcome.SUCCESS for o in self.source_outcomes)
