"""Tests for the Layer 2 CLI scaffold and error hierarchy (Stage 0)."""

from __future__ import annotations

from typer.testing import CliRunner

from locus import __version__
from locus.cli import app
from locus.errors import (
    BackendUnavailableError,
    ConfigError,
    CycleError,
    ImageNotFoundError,
    LocusRuntimeError,
    PlanError,
    TypeMismatchError,
)

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    # Typer's no_args_is_help exits with code 2 and prints usage.
    assert result.exit_code == 2
    assert "Usage" in result.stdout


def test_error_hierarchy() -> None:
    assert issubclass(ConfigError, LocusRuntimeError)
    assert issubclass(CycleError, PlanError)
    assert issubclass(TypeMismatchError, PlanError)
    assert issubclass(PlanError, LocusRuntimeError)


def test_cycle_error_message() -> None:
    err = CycleError(["a", "b", "a"])
    assert err.cycle == ["a", "b", "a"]
    assert "a -> b -> a" in str(err)


def test_type_mismatch_error_message() -> None:
    err = TypeMismatchError("ocr", "dedup", "ir/v1", ["table/v1"])
    assert "ocr" in str(err) and "dedup" in str(err)
    assert "table/v1" in str(err)


def test_image_not_found_and_backend_errors() -> None:
    assert "doc-to-tables:1.0" in str(ImageNotFoundError("doc-to-tables:1.0"))
    assert "docker" in str(BackendUnavailableError("docker"))
