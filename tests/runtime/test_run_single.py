"""Tests for single-image run via the process backend (Stage 3)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from locus.builtins import resolve_builtin
from locus.cli import app
from locus.errors import ImageNotFoundError
from locus.locusfile import Locusfile, SourceSpec
from locus.runner import resolve_image, run_single
from locus.workspace import RunWorkspace

ENGINE_FIXTURES = Path(__file__).parent.parent / "fixtures"
runner = CliRunner()


def test_resolve_builtin_doc_to_tables() -> None:
    image = resolve_builtin("doc-to-tables:0.1.0")
    assert image is not None
    assert image.manifest.name == "doc-to-tables"
    assert image.manifest.emits.tag() == "table/v1"


def test_resolve_unknown_image_raises() -> None:
    with pytest.raises(ImageNotFoundError):
        resolve_image("does-not-exist:1.0")


def test_run_single_over_csv_produces_grounded_table() -> None:
    lf = Locusfile(
        image="doc-to-tables:0.1.0",
        source=SourceSpec(type="files", path=str(ENGINE_FIXTURES / "invoices.csv")),
    )
    out = run_single(lf, workspace=RunWorkspace())
    assert out.engine_mode == "deterministic"
    assert len(out.frame) == 3
    assert "_lineage" in out.frame.columns
    # artifact materialized as a parquet file
    assert out.artifact.payload_path.endswith(".parquet")
    back = pd.read_parquet(out.artifact.payload_path)
    assert len(back) == 3


def test_workspace_content_hash_stable() -> None:
    ws = RunWorkspace()
    assert ws.content_hash("a", "b") == ws.content_hash("a", "b")
    assert ws.content_hash("a", "b") != ws.content_hash("a", "c")


def test_cli_run_end_to_end(tmp_path: Path) -> None:
    lf = tmp_path / "locusfile.yaml"
    lf.write_text(
        f"image: doc-to-tables:0.1.0\n"
        f"source:\n  type: files\n  path: {ENGINE_FIXTURES / 'invoices.csv'}\n"
    )
    out_csv = tmp_path / "out.csv"
    result = runner.invoke(app, ["run", str(lf), "--export", str(out_csv)])
    assert result.exit_code == 0, result.stdout
    assert "Produced 3 row(s)" in result.stdout
    assert out_csv.exists()
