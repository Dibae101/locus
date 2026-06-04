"""Tests for run result and per-source outcome records (Stage 0.2)."""

from __future__ import annotations

from locus_engine.results import Outcome, RunResult, SourceOutcome


def test_empty_run_is_not_corpus_success() -> None:
    assert RunResult().corpus_success is False


def test_corpus_success_with_one_success_among_errors() -> None:
    """Req 11.5: corpus succeeds if at least one source succeeds."""
    rr = RunResult()
    rr.record(SourceOutcome(source_id="a", outcome=Outcome.ERROR, reason="parse fail"))
    rr.record(SourceOutcome(source_id="b", outcome=Outcome.SUCCESS))
    rr.record(SourceOutcome(source_id="c", outcome=Outcome.SKIPPED))

    assert rr.corpus_success is True
    assert rr.sources_processed == 3
    assert [o.source_id for o in rr.succeeded] == ["b"]
    assert [o.source_id for o in rr.errored] == ["a"]


def test_all_errors_is_not_success() -> None:
    rr = RunResult()
    rr.record(SourceOutcome(source_id="a", outcome=Outcome.ERROR))
    rr.record(SourceOutcome(source_id="b", outcome=Outcome.ERROR))
    assert rr.corpus_success is False


def test_counts_default_zero() -> None:
    rr = RunResult()
    assert (rr.rows_emitted, rr.rows_flagged, rr.rows_rejected) == (0, 0, 0)
