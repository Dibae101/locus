"""Observability (Stage 2.4).

Structured events for each processing step, surfaced through a configurable sink.
Per-phase events (Req 11.1), error events (Req 11.2), and a corpus summary
(Req 11.4) are emitted; the sink is configurable (Req 11.3).

Requirements: 11.1, 11.2, 11.3, 11.4.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    INFO = "info"
    ERROR = "error"


class ObservabilityEvent(BaseModel):
    """A structured record describing a processing step."""

    phase: str
    source_id: str | None = None
    severity: Severity = Severity.INFO
    start_time: float | None = None
    end_time: float | None = None
    outcome: str | None = None
    reason: str | None = None
    detail: dict[str, object] = Field(default_factory=dict)

    @property
    def duration(self) -> float | None:
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time


# A sink receives each emitted event.
Sink = Callable[[ObservabilityEvent], None]


def logging_sink(event: ObservabilityEvent) -> None:
    """Default sink: route to the standard library logger."""
    logger = logging.getLogger("locus_engine")
    level = logging.ERROR if event.severity is Severity.ERROR else logging.INFO
    logger.log(level, "%s", event.model_dump(exclude_none=True))


class ObservabilityBus:
    """Collects events and forwards them to a configurable sink (Req 11.3)."""

    def __init__(self, sink: Sink | None = None, *, capture: bool = True) -> None:
        self._sink = sink or logging_sink
        self._capture = capture
        self.events: list[ObservabilityEvent] = []

    def emit(self, event: ObservabilityEvent) -> None:
        if self._capture:
            self.events.append(event)
        self._sink(event)

    @contextmanager
    def phase(self, phase: str, source_id: str | None = None) -> Iterator[None]:
        """Time a phase and emit a completion event (Req 11.1)."""
        start = time.time()
        try:
            yield
        finally:
            self.emit(
                ObservabilityEvent(
                    phase=phase,
                    source_id=source_id,
                    start_time=start,
                    end_time=time.time(),
                    outcome="completed",
                )
            )

    def error(self, phase: str, reason: str, source_id: str | None = None) -> None:
        """Emit an error event (Req 11.2)."""
        self.emit(
            ObservabilityEvent(
                phase=phase,
                source_id=source_id,
                severity=Severity.ERROR,
                outcome="error",
                reason=reason,
            )
        )

    def corpus_summary(
        self,
        *,
        sources_processed: int,
        rows_emitted: int,
        rows_flagged: int,
        rows_rejected: int,
        success: bool,
    ) -> None:
        """Emit the end-of-corpus summary event (Req 11.4)."""
        self.emit(
            ObservabilityEvent(
                phase="corpus",
                outcome="success" if success else "failure",
                detail={
                    "sources_processed": sources_processed,
                    "rows_emitted": rows_emitted,
                    "rows_flagged": rows_flagged,
                    "rows_rejected": rows_rejected,
                },
            )
        )
