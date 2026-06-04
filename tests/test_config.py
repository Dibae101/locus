"""Tests for pipeline configuration (Stage 2.3)."""

from __future__ import annotations

import pytest

from locus_engine.config import PipelineConfig
from locus_engine.errors import ConfigError


def test_defaults_applied() -> None:
    """Req 12.2, 12.5: only source required; defaults fill the rest."""
    cfg = PipelineConfig.load({"source": {"type": "files", "path": "./in"}})
    assert cfg.schema_mode == "infer"
    assert cfg.retry_limit == 2
    assert cfg.grounding_threshold == 0.7
    assert cfg.rejection_mode == "flag"
    assert cfg.dedup.enabled is False
    assert cfg.output_format == "dataframe"


def test_out_of_range_threshold_raises_config_error() -> None:
    """Req 12.3: range violation names the setting."""
    with pytest.raises(ConfigError) as ei:
        PipelineConfig.load(
            {"source": {"type": "files", "path": "./in"}, "grounding_threshold": 1.5}
        )
    assert "grounding_threshold" in str(ei.value)


def test_negative_retry_limit_raises() -> None:
    with pytest.raises(ConfigError) as ei:
        PipelineConfig.load(
            {"source": {"type": "files", "path": "./in"}, "retry_limit": -1}
        )
    assert "retry_limit" in str(ei.value)


def test_missing_source_raises() -> None:
    with pytest.raises(ConfigError):
        PipelineConfig.load({})


def test_invalid_enum_value_raises() -> None:
    with pytest.raises(ConfigError) as ei:
        PipelineConfig.load(
            {"source": {"type": "files"}, "rejection_mode": "destroy"}
        )
    assert "rejection_mode" in str(ei.value)
