"""OCI/Harbor-backed image store (Layer 2, OCI backend).

Implements the same ``ImageStore`` protocol as ``LocalImageStore`` but against a real
OCI registry (Harbor, GHCR, ECR, ...) via the ``oras`` client. A Locus image is pushed
as an OCI artifact: the packed ``.tar.gz`` (manifest + payload) plus the manifest JSON
as artifact annotations so ``search``/``inspect`` can read metadata without pulling the
full blob.

Because the CLI depends only on the ``ImageStore`` protocol, switching from the local
store to this one is a configuration change. ``oras`` is an optional ``oci`` extra; it
is imported lazily so the core stays light.

Requirements: 2.1, 2.2, 2.4, 2.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.7, 11.1, 11.2.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from locus.errors import ImageNotFoundError, LocusRuntimeError
from locus.manifest import ImageManifest
from locus.packaging import pack_image, read_manifest, unpack_image
from locus.store import ImageSummary, split_ref

ARTIFACT_TYPE = "application/vnd.locus.image.v1+gzip"
MANIFEST_ANNOTATION = "io.locus.manifest"
VISIBILITY_ANNOTATION = "io.locus.visibility"


class OrasImageStore:
    """OCI-registry-backed image store. Conforms to the ImageStore protocol.

    ``registry`` is the host (e.g. ``hub.locus.dev`` or ``ghcr.io``); image refs are
    ``name:version`` and resolve to ``<registry>/<namespace>/<name>:<version>``.
    """

    def __init__(
        self,
        registry: str,
        namespace: str = "library",
        *,
        cache_dir: str | Path | None = None,
        insecure: bool = False,
        client: Any | None = None,
    ) -> None:
        self._registry = registry.rstrip("/")
        self._namespace = namespace
        self._cache = Path(cache_dir) if cache_dir else Path.home() / ".locus" / "oci-cache"
        self._cache.mkdir(parents=True, exist_ok=True)
        self._insecure = insecure
        self._client = client  # injectable for tests

    # --- client ----------------------------------------------------------

    def _oras(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import oras.client
        except ImportError as exc:  # pragma: no cover - exercised when extra missing
            raise LocusRuntimeError(
                "OCI registry support requires the 'oci' extra: pip install locus[oci]"
            ) from exc
        self._client = oras.client.OrasClient(hostname=self._registry, insecure=self._insecure)
        return self._client

    def login(self, username: str, password: str) -> None:
        """Authenticate to the registry (Req 10.1). Distinct from any LLM key."""
        self._oras().login(username=username, password=password, hostname=self._registry)

    # --- ref helpers -----------------------------------------------------

    def _target(self, name: str, version: str) -> str:
        return f"{self._registry}/{self._namespace}/{name}:{version}"

    def resolve_version(self, name: str, version: str | None) -> str:
        if version is not None:
            return version
        tags = self._tags(name)
        if not tags:
            raise ImageNotFoundError(name)
        from packaging.version import InvalidVersion, Version

        try:
            return max(tags, key=Version)
        except InvalidVersion:
            return sorted(tags)[-1]

    def _tags(self, name: str) -> list[str]:
        try:
            return list(self._oras().get_tags(f"{self._registry}/{self._namespace}/{name}"))
        except Exception:
            return []

    # --- push ------------------------------------------------------------

    def push(self, image_dir: Path, *, private: bool = False) -> str:
        manifest = read_manifest(image_dir)
        with tempfile.TemporaryDirectory() as tmp:
            archive = pack_image(image_dir, Path(tmp) / f"{manifest.name}.tar.gz")
            target = self._target(manifest.name, manifest.version)
            annotations = {
                MANIFEST_ANNOTATION: manifest.model_dump_json(),
                VISIBILITY_ANNOTATION: "private" if private else "public",
            }
            self._oras().push(
                target=target,
                files=[f"{archive}:{ARTIFACT_TYPE}"],
                manifest_annotations=annotations,
                disable_path_validation=True,
            )
        return manifest.ref

    # --- pull / cache ----------------------------------------------------

    def cached(self, ref: str) -> Path | None:
        name, version = split_ref(ref)
        if version is None:
            return None
        cached = self._cache / name / version
        return cached if (cached / "manifest.json").exists() else None

    def pull(self, ref: str) -> Path:
        name, requested = split_ref(ref)
        version = self.resolve_version(name, requested)
        dest = self._cache / name / version
        if (dest / "manifest.json").exists():
            return dest  # cache hit (Req 2.2)

        target = self._target(name, version)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                self._oras().pull(target=target, outdir=tmp, overwrite=True)
            except Exception as exc:
                raise ImageNotFoundError(f"{name}:{version}") from exc
            archives = list(Path(tmp).glob("*.tar.gz"))
            if not archives:
                raise ImageNotFoundError(f"{name}:{version}")
            dest.mkdir(parents=True, exist_ok=True)
            unpack_image(archives[0], dest)
        return dest

    # --- search / inspect ------------------------------------------------

    def _manifest_from_annotations(self, name: str, version: str) -> tuple[ImageManifest, bool]:
        target = self._target(name, version)
        oci_manifest = self._oras().get_manifest(target)
        annotations = (oci_manifest or {}).get("annotations", {}) or {}
        raw = annotations.get(MANIFEST_ANNOTATION)
        if not raw:
            raise ImageNotFoundError(f"{name}:{version}")
        manifest = ImageManifest.model_validate(json.loads(raw))
        private = annotations.get(VISIBILITY_ANNOTATION) == "private"
        return manifest, private

    def inspect(self, ref: str, *, include_private: bool = True) -> ImageManifest:
        name, requested = split_ref(ref)
        version = self.resolve_version(name, requested)
        manifest, private = self._manifest_from_annotations(name, version)
        if private and not include_private:
            raise ImageNotFoundError(f"{name}:{version}")
        return manifest

    def search(self, query: str = "", *, include_private: bool = True) -> list[ImageSummary]:
        # OCI registries have no standard cross-repo catalog search; this lists tags
        # for a queried repository name. A hub-side index API supersedes this later.
        if not query:
            return []
        out: list[ImageSummary] = []
        for version in self._tags(query):
            try:
                manifest, private = self._manifest_from_annotations(query, version)
            except Exception:
                continue
            if private and not include_private:
                continue
            out.append(
                ImageSummary(
                    name=manifest.name,
                    version=manifest.version,
                    emits=manifest.emits.tag(),
                    accepts=[a.tag() for a in manifest.accepts],
                    privacy_class=manifest.privacy_class,
                    provenance_conformant=manifest.provenance_conformant,
                    private=private,
                )
            )
        return out
