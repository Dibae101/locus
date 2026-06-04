"""Local file system connector (Stage 3.1).

Reads a file path and produces a ``RawSource`` with a stable, unique source id and a
detected content type.

Requirements: 1.1, 1.2, 1.3.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from locus_engine.errors import ConnectorError
from locus_engine.plugins import RawSource, SourceRef

# Extension-based content types we care about, beyond what mimetypes knows.
_EXTRA_TYPES = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".html": "text/html",
    ".htm": "text/html",
    ".json": "application/json",
    ".txt": "text/plain",
}


def detect_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _EXTRA_TYPES:
        return _EXTRA_TYPES[ext]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


class FileConnector:
    """Connector for local file system paths."""

    name = "file"

    def supports(self, ref: SourceRef) -> bool:
        if ref.kind == "file":
            return True
        if ref.kind not in (None, "files"):
            return False
        # Treat refs that resolve to an existing local path as supported.
        return Path(ref.uri).expanduser().exists()

    def read(self, ref: SourceRef) -> RawSource:
        path = Path(ref.uri).expanduser()
        if not path.exists() or not path.is_file():
            raise ConnectorError(ref.uri, "file not found")
        try:
            data = path.read_bytes()
        except OSError as exc:  # pragma: no cover - exercised via error path
            raise ConnectorError(ref.uri, f"read failed: {exc}") from exc
        return RawSource(
            source_id=str(path.resolve()),
            content_type=detect_content_type(path),
            data=data,
        )
