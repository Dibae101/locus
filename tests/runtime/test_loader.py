"""Tests for Locusfile loading + credential safety (Stage 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from locus.errors import ConfigError, CredentialError
from locus.loader import ensure_env_gitignored, load_locusfile


def _write(p: Path, text: str) -> Path:
    p.write_text(text)
    return p


def test_load_minimal_single_image(tmp_path: Path) -> None:
    lf_path = _write(
        tmp_path / "locusfile.yaml",
        "image: doc-to-tables:1.0\nsource:\n  type: files\n  path: ./data\n",
    )
    lf = load_locusfile(lf_path)
    assert lf.image == "doc-to-tables:1.0"
    assert len(lf.normalized_pipeline()) == 1


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_locusfile(tmp_path / "nope.yaml")


def test_missing_source_raises(tmp_path: Path) -> None:
    lf_path = _write(tmp_path / "locusfile.yaml", "image: doc-to-tables:1.0\n")
    with pytest.raises(ConfigError) as ei:
        load_locusfile(lf_path)
    assert "source" in str(ei.value)


def test_missing_image_and_pipeline_raises(tmp_path: Path) -> None:
    lf_path = _write(tmp_path / "locusfile.yaml", "source:\n  type: files\n  path: ./d\n")
    with pytest.raises(ConfigError):
        load_locusfile(lf_path)


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    lf_path = _write(tmp_path / "locusfile.yaml", "image: [unclosed\n")
    with pytest.raises(ConfigError):
        load_locusfile(lf_path)


def test_raw_key_in_llm_rejected(tmp_path: Path) -> None:
    """Req 4.3."""
    lf_path = _write(
        tmp_path / "locusfile.yaml",
        "image: x:1.0\n"
        "source:\n  type: files\n  path: ./d\n"
        "llm:\n  provider: openai\n  api_key: sk-abcdefghijklmnop1234567890\n",
    )
    with pytest.raises(CredentialError):
        load_locusfile(lf_path)


def test_env_reference_is_allowed(tmp_path: Path) -> None:
    lf_path = _write(
        tmp_path / "locusfile.yaml",
        "image: x:1.0\n"
        "source:\n  type: files\n  path: ./d\n"
        "llm:\n  provider: openai\n  api_key: ${OPENAI_API_KEY}\n",
    )
    lf = load_locusfile(lf_path)
    assert lf.llm is not None


def test_ensure_env_gitignored_creates_and_appends(tmp_path: Path) -> None:
    ensure_env_gitignored(tmp_path)
    gi = (tmp_path / ".gitignore").read_text()
    assert ".env" in gi
    # idempotent
    ensure_env_gitignored(tmp_path)
    assert (tmp_path / ".gitignore").read_text().count(".env") == 1
