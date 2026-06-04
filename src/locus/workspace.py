"""Run workspace and artifact serialization (Layer 2, Stage 3.2).

A run-scoped working directory where intermediate ``LocusArtifact`` payloads are
materialized as Parquet files and lineage as JSON. Passing artifacts by file enables
the Docker backend, large datasets, and content-addressed stage caching.

Requirements: 6.2, 5.8.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd

from locus.artifacts import ArtifactType, LocusArtifact


class RunWorkspace:
    """Owns the temp directory for one pipeline run."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            self._dir = Path(tempfile.mkdtemp(prefix="locus-run-"))
            self._owns = True
        else:
            self._dir = Path(root)
            self._dir.mkdir(parents=True, exist_ok=True)
            self._owns = False

    @property
    def path(self) -> Path:
        return self._dir

    def write_table(
        self,
        stage_id: str,
        frame: pd.DataFrame,
        artifact_type: ArtifactType,
        *,
        engine_mode: str = "deterministic",
        lineage: object | None = None,
    ) -> LocusArtifact:
        payload = self._dir / f"{stage_id}.parquet"
        frame.to_parquet(payload, index=False)
        lineage_path: str | None = None
        if lineage is not None:
            lp = self._dir / f"{stage_id}.lineage.json"
            lp.write_text(json.dumps(lineage, default=str))
            lineage_path = str(lp)
        return LocusArtifact(
            type=artifact_type,
            payload_path=str(payload),
            lineage_path=lineage_path,
            produced_by=stage_id,
            engine_mode=engine_mode,
        )

    def read_table(self, artifact: LocusArtifact) -> pd.DataFrame:
        return pd.read_parquet(artifact.payload_path)

    @staticmethod
    def content_hash(*parts: str) -> str:
        """Stable hash for stage caching (input fingerprint + image ref)."""
        h = hashlib.sha256()
        for p in parts:
            h.update(p.encode())
            h.update(b"\x00")
        return h.hexdigest()[:16]
