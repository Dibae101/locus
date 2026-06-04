"""Image building and conformance certification (Layer 2, Stage 7).

Builds a publishable image from an ``ImageManifest`` (read from a YAML manifest
file): pins dependency/config versions for reproducibility and certifies
provenance-conformance by probing the capability with a known provenanced input.
A capability that preserves the ``_lineage`` column is certified conformant; one that
drops it is recorded non-conformant.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from locus.emit_constants import LINEAGE_COLUMN
from locus.errors import ConfigError
from locus.image import StageContext
from locus.manifest import ImageManifest
from locus.packaging import write_image_dir


def load_manifest(path: str | Path) -> ImageManifest:
    p = Path(path).expanduser()
    if not p.exists():
        raise ConfigError(f"image manifest not found: {p}")
    try:
        data = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {p}: {exc}") from exc
    return ImageManifest.model_validate(data)


def _pinned_versions(packages: list[str]) -> dict[str, str]:
    """Pin the installed versions of the named packages for reproducibility (Req 9.3)."""
    from importlib.metadata import PackageNotFoundError, version

    pinned: dict[str, str] = {}
    for pkg in packages:
        try:
            pinned[pkg] = version(pkg)
        except PackageNotFoundError:
            continue
    pinned["python"] = f"{sys.version_info.major}.{sys.version_info.minor}"
    return pinned


def certify_conformance(capability: object) -> bool:
    """Probe a table->table capability: feed a provenanced frame and verify the
    output preserves per-cell lineage (Req 9.4). Returns True if conformant.

    Root capabilities (no ``run`` over a table) are certified separately via the
    engine's own conformance harness; here we check the lineage-preservation
    contract that composition relies on.
    """
    run = getattr(capability, "run", None)
    if not callable(run):
        return False

    probe = pd.DataFrame(
        {
            "value": ["x"],
            LINEAGE_COLUMN: [
                {
                    "_row_flagged": False,
                    "value": {
                        "faithfulness": 1.0,
                        "grounding_mode": "degraded",
                        "locations": [{"source_id": "probe", "index": 0}],
                    },
                }
            ],
        }
    )
    ctx = StageContext(stage_id="_probe", source=None)
    try:
        out, _ = run([probe], ctx)
    except Exception:
        return False
    if not isinstance(out, pd.DataFrame) or LINEAGE_COLUMN not in out.columns:
        return False
    # The lineage payload must still reference the probe source.
    for lin in out[LINEAGE_COLUMN]:
        if isinstance(lin, dict):
            for meta in lin.values():
                if isinstance(meta, dict) and meta.get("locations"):
                    return True
    return False


def build_image(
    manifest_path: str | Path,
    *,
    capability: object | None = None,
    output_dir: str | Path | None = None,
    pin_packages: list[str] | None = None,
) -> Path:
    """Build a publishable image directory from a manifest (Req 9.1)."""
    manifest = load_manifest(manifest_path)
    manifest.dependencies = {
        **manifest.dependencies,
        **_pinned_versions(pin_packages or ["locus-etl", "pydantic", "pandas"]),
    }
    if capability is not None:
        manifest.provenance_conformant = certify_conformance(capability)

    out = Path(output_dir) if output_dir else Path(f"./{manifest.name}-{manifest.version}")
    payload = {"manifest_source": Path(manifest_path).read_bytes()}
    return write_image_dir(out, manifest, payload)
