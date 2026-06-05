"""Tests for the expose: field and the result visualization (column profiles)."""

from __future__ import annotations

from pathlib import Path

import pytest

from locus.locusfile import ExposeSpec, Locusfile, SourceSpec

CSV = str(Path(__file__).parent.parent / "fixtures" / "invoices.csv")


# --- expose: field coercion -----------------------------------------------


def test_expose_int_shorthand() -> None:
    lf = Locusfile.model_validate(
        {"image": "doc-to-tables:0.1.0", "source": {"type": "files", "path": CSV},
         "expose": 9000}
    )
    assert isinstance(lf.expose, ExposeSpec)
    assert lf.expose.port == 9000
    assert lf.expose.host == "127.0.0.1"
    assert lf.expose.open is False


def test_expose_full_mapping() -> None:
    lf = Locusfile.model_validate(
        {"image": "doc-to-tables:0.1.0", "source": {"type": "files", "path": CSV},
         "expose": {"port": 8123, "host": "0.0.0.0", "open": True}}
    )
    assert lf.expose is not None
    assert lf.expose.port == 8123
    assert lf.expose.host == "0.0.0.0"
    assert lf.expose.open is True


def test_expose_absent_is_none() -> None:
    lf = Locusfile.model_validate(
        {"image": "doc-to-tables:0.1.0", "source": {"type": "files", "path": CSV}}
    )
    assert lf.expose is None


def test_expose_invalid_type_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Locusfile.model_validate(
            {"image": "doc-to-tables:0.1.0",
             "source": {"type": "files", "path": CSV}, "expose": "not-a-port"}
        )


# --- visualization payload (needs the serve extra) ------------------------

pytest.importorskip("fastapi")

from locus.runner import run_pipeline  # noqa: E402
from locus.serve import (  # noqa: E402
    build_column_profiles,
    build_result_payload,
    render_html,
)
from locus.workspace import RunWorkspace  # noqa: E402


def _run():
    lf = Locusfile(image="doc-to-tables:0.1.0", source=SourceSpec(type="files", path=CSV))
    return run_pipeline(lf, workspace=RunWorkspace())


def test_payload_includes_profiles() -> None:
    payload = build_result_payload(_run())
    profiles = {p["name"]: p for p in payload["profiles"]}
    # invoices.csv has invoice_number, vendor, total
    assert "total" in profiles
    assert profiles["total"]["kind"] == "numeric"
    assert "histogram" in profiles["total"]
    assert profiles["total"]["mean"] is not None
    assert profiles["vendor"]["kind"] == "categorical"
    assert profiles["vendor"]["top_values"]


def test_profile_fill_rate_and_unique() -> None:
    out = _run()
    profiles = build_column_profiles(
        out.frame, [c for c in out.frame.columns if c != "_lineage"]
    )
    for p in profiles:
        assert 0.0 <= p["fill_rate"] <= 1.0
        assert p["unique"] >= 0


def test_html_has_charts_section() -> None:
    html = render_html(build_result_payload(_run()))
    assert "Visualize" in html
    assert "bar-fill" in html  # a chart bar was rendered
    assert "Data &amp; provenance" in html
