"""Extraction errors (e.g. an image needing OCR) must surface to the run output and
the result UI, so a 0-row result explains itself instead of showing a blank page."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from locus.locusfile import Locusfile, SourceSpec
from locus.runner import run_pipeline
from locus.workspace import RunWorkspace


def _run(path: str):
    lf = Locusfile(image="doc-to-tables:0.1.0", source=SourceSpec(type="files", path=path))
    return run_pipeline(lf, workspace=RunWorkspace())


def test_image_error_surfaces_in_warnings(tmp_path: Path) -> None:
    png = tmp_path / "x.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)  # not a real image; routed by ext
    out = _run(str(png))
    assert len(out.frame) == 0
    assert any("OCR" in w for w in out.warnings)


def test_unparseable_zip_surfaces_reason(tmp_path: Path) -> None:
    # A zip with only binary members yields no parseable content -> a clear reason.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("blob.bin", b"\x00\x01\x02\x03")
    z = tmp_path / "empty.zip"
    z.write_bytes(buf.getvalue())
    out = _run(str(z))
    assert len(out.frame) == 0
    assert out.warnings  # some explanation present


def test_result_ui_shows_no_rows_notice(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    from locus.serve import build_result_payload, render_html

    png = tmp_path / "y.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    out = _run(str(png))
    html = render_html(build_result_payload(out))
    assert "No rows were produced" in html
    assert "OCR" in html
