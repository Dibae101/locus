"""Tests for observability (Stage 2.4)."""

from __future__ import annotations

from locus_engine.observability import ObservabilityBus, Severity


def test_phase_emits_completion_event_with_timing() -> None:
    bus = ObservabilityBus(sink=lambda e: None)
    with bus.phase("parse", source_id="doc-1"):
        pass
    assert len(bus.events) == 1
    ev = bus.events[0]
    assert ev.phase == "parse"
    assert ev.source_id == "doc-1"
    assert ev.outcome == "completed"
    assert ev.duration is not None and ev.duration >= 0


def test_error_event() -> None:
    bus = ObservabilityBus(sink=lambda e: None)
    bus.error("extract", "schema validation failed", source_id="doc-2")
    ev = bus.events[0]
    assert ev.severity is Severity.ERROR
    assert ev.reason == "schema validation failed"


def test_corpus_summary_counts() -> None:
    bus = ObservabilityBus(sink=lambda e: None)
    bus.corpus_summary(
        sources_processed=3,
        rows_emitted=10,
        rows_flagged=2,
        rows_rejected=1,
        success=True,
    )
    ev = bus.events[0]
    assert ev.phase == "corpus"
    assert ev.outcome == "success"
    assert ev.detail["sources_processed"] == 3
    assert ev.detail["rows_flagged"] == 2


def test_custom_sink_receives_events() -> None:
    received = []
    bus = ObservabilityBus(sink=received.append)
    bus.error("ingest", "boom")
    assert len(received) == 1
    assert received[0].reason == "boom"
