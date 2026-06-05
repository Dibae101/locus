"""Tests for declarative + CLI result export (csv/parquet/json/markdown)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from locus.cli import app
from locus.errors import ConfigError
from locus.export import infer_format, resolve_format, write_export

ENGINE_FIXTURES = Path(__file__).parent.parent / "fixtures"
runner = CliRunner()


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"name": ["Acme", "Globex"], "amount": [100, 200]})


def test_infer_format_from_extension() -> None:
    assert infer_format("out.csv") == "csv"
    assert infer_format("out.parquet") == "parquet"
    assert infer_format("out.json") == "json"
    assert infer_format("out.md") == "markdown"
    assert infer_format("out.unknown") is None


def test_resolve_format_precedence() -> None:
    # Explicit declaration wins over the extension.
    assert resolve_format("out.csv", "json") == "json"
    # Falls back to extension inference.
    assert resolve_format("out.parquet", None) == "parquet"
    # Defaults to csv when neither is known.
    assert resolve_format("out.dat", None) == "csv"


def test_resolve_format_rejects_unsupported() -> None:
    with pytest.raises(ConfigError):
        resolve_format("out.csv", "xlsx")


def test_write_each_format(tmp_path: Path) -> None:
    frame = _frame()

    csv_path = tmp_path / "out.csv"
    write_export(frame, str(csv_path), "csv")
    assert pd.read_csv(csv_path).shape == (2, 2)

    pq_path = tmp_path / "out.parquet"
    write_export(frame, str(pq_path), "parquet")
    assert pd.read_parquet(pq_path).shape == (2, 2)

    json_path = tmp_path / "out.json"
    write_export(frame, str(json_path), "json")
    records = json.loads(json_path.read_text())
    assert records[0]["name"] == "Acme"

    md_path = tmp_path / "out.md"
    write_export(frame, str(md_path), "markdown")
    text = md_path.read_text()
    assert "| name | amount |" in text
    assert "| --- | --- |" in text
    assert "| Acme | 100 |" in text


def test_markdown_escapes_pipes(tmp_path: Path) -> None:
    frame = pd.DataFrame({"a": ["x|y"]})
    md_path = tmp_path / "out.md"
    write_export(frame, str(md_path), "markdown")
    assert "x\\|y" in md_path.read_text()


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "out.csv"
    write_export(_frame(), str(nested), "csv")
    assert nested.exists()


def test_cli_export_from_locusfile_field(tmp_path: Path) -> None:
    """export declared in the Locusfile (no --export flag) is honored."""
    out_json = tmp_path / "result.json"
    lf = tmp_path / "locusfile.yaml"
    lf.write_text(
        "image: doc-to-tables:0.1.0\n"
        f"source:\n  type: files\n  path: {ENGINE_FIXTURES / 'invoices.csv'}\n"
        f"export:\n  path: {out_json}\n  format: json\n"
    )
    result = runner.invoke(app, ["run", str(lf)])
    assert result.exit_code == 0, result.stdout
    assert "Exported to" in result.stdout
    assert "(json)" in result.stdout
    assert out_json.exists()
    assert isinstance(json.loads(out_json.read_text()), list)


def test_cli_export_infers_format_from_locusfile_path(tmp_path: Path) -> None:
    out_md = tmp_path / "result.md"
    lf = tmp_path / "locusfile.yaml"
    lf.write_text(
        "image: doc-to-tables:0.1.0\n"
        f"source:\n  type: files\n  path: {ENGINE_FIXTURES / 'invoices.csv'}\n"
        f"export:\n  path: {out_md}\n"
    )
    result = runner.invoke(app, ["run", str(lf)])
    assert result.exit_code == 0, result.stdout
    assert "(markdown)" in result.stdout
    assert out_md.read_text().startswith("|")


def test_cli_flag_overrides_locusfile_export(tmp_path: Path) -> None:
    """--export path takes precedence over the Locusfile export.path."""
    declared = tmp_path / "declared.csv"
    override = tmp_path / "override.json"
    lf = tmp_path / "locusfile.yaml"
    lf.write_text(
        "image: doc-to-tables:0.1.0\n"
        f"source:\n  type: files\n  path: {ENGINE_FIXTURES / 'invoices.csv'}\n"
        f"export:\n  path: {declared}\n  format: csv\n"
    )
    result = runner.invoke(
        app, ["run", str(lf), "--export", str(override), "--format", "json"]
    )
    assert result.exit_code == 0, result.stdout
    assert override.exists()
    assert not declared.exists()


def test_cli_rejects_unsupported_format(tmp_path: Path) -> None:
    out = tmp_path / "out.xlsx"
    lf = tmp_path / "locusfile.yaml"
    lf.write_text(
        "image: doc-to-tables:0.1.0\n"
        f"source:\n  type: files\n  path: {ENGINE_FIXTURES / 'invoices.csv'}\n"
    )
    result = runner.invoke(app, ["run", str(lf), "--export", str(out), "--format", "xlsx"])
    assert result.exit_code != 0
