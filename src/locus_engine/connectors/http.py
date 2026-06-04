"""HTTP/URL and REST API connectors (Stage 9.1).

``HttpConnector`` fetches an HTTP(S) URL with the standard library (no heavy deps).
``RestApiConnector`` fetches a JSON endpoint and yields structured records. Auth
tokens arrive via the connector config (Req 1.6). Both isolate failures as
``ConnectorError`` so the pipeline continues (Req 1.5).

Requirements: 1.1, 1.2, 1.3, 1.6.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from locus_engine.errors import ConnectorError
from locus_engine.plugins import RawSource, SourceRef


def _fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers=headers)  # noqa: S310 (https enforced below)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        content_type = resp.headers.get_content_type()
        return resp.read(), content_type


class HttpConnector:
    """Fetches content from an HTTP(S) URL."""

    name = "http"

    def __init__(self, headers: dict[str, str] | None = None, timeout: float = 30.0) -> None:
        self._headers = headers or {}
        self._timeout = timeout

    def supports(self, ref: SourceRef) -> bool:
        if ref.kind in ("url", "http"):
            return True
        return ref.uri.startswith(("http://", "https://"))

    def read(self, ref: SourceRef) -> RawSource:
        if not ref.uri.startswith(("http://", "https://")):
            raise ConnectorError(ref.uri, "not an http(s) url")
        try:
            data, content_type = _fetch(ref.uri, self._headers, self._timeout)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ConnectorError(ref.uri, f"fetch failed: {exc}") from exc
        return RawSource(source_id=ref.uri, content_type=content_type, data=data)


class RestApiConnector:
    """Fetches a JSON REST endpoint and yields structured records."""

    name = "rest"

    def __init__(
        self,
        headers: dict[str, str] | None = None,
        records_path: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._headers = {"Accept": "application/json", **(headers or {})}
        self._records_path = records_path  # dotted path to the list of records
        self._timeout = timeout

    def supports(self, ref: SourceRef) -> bool:
        return ref.kind in ("api", "rest")

    def read(self, ref: SourceRef) -> RawSource:
        try:
            data, _ = _fetch(ref.uri, self._headers, self._timeout)
            payload = json.loads(data)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ConnectorError(ref.uri, f"api fetch failed: {exc}") from exc

        records = self._extract_records(payload)
        return RawSource(
            source_id=ref.uri, content_type="application/json", records=records
        )

    def _extract_records(self, payload: Any) -> list[dict[str, Any]]:
        node = payload
        if self._records_path:
            for part in self._records_path.split("."):
                node = node[part]
        if isinstance(node, list):
            return [r for r in node if isinstance(r, dict)]
        if isinstance(node, dict):
            return [node]
        raise ConnectorError("<api>", "could not locate records list in response")
