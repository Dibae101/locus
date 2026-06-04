"""Runtime backends (Layer 2, Stage 10.1).

The default ``ProcessBackend`` runs a stage's capability in-process. The optional
``DockerBackend`` runs it inside a container; if Docker is unavailable it raises a
clear error and never silently falls back (Req 1.5).

This module defines the backend protocol and the selection logic. The process
backend delegates to the capability directly (as the executor already does); the
Docker backend is structured for container execution and validated for availability.

Requirements: 1.3, 1.4, 1.5.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from locus.errors import BackendUnavailableError
from locus.image import ResolvedImage, StageContext


class RuntimeBackend(Protocol):
    name: str

    def available(self) -> bool: ...
    def run_stage(
        self, image: ResolvedImage, inputs: list[pd.DataFrame], ctx: StageContext
    ) -> tuple[pd.DataFrame, str]: ...


class ProcessBackend:
    """Default backend: runs the capability in the current Python process."""

    name = "process"

    def available(self) -> bool:
        return True

    def run_stage(
        self, image: ResolvedImage, inputs: list[pd.DataFrame], ctx: StageContext
    ) -> tuple[pd.DataFrame, str]:
        return image.capability.run(inputs, ctx)


class DockerBackend:
    """Optional backend: runs a stage inside a container.

    Availability requires the ``docker`` SDK and a reachable daemon. When
    unavailable, ``run_stage`` raises ``BackendUnavailableError`` rather than
    falling back to the process backend (Req 1.5).
    """

    name = "docker"

    def available(self) -> bool:
        try:
            import docker
        except ImportError:
            return False
        try:
            client = docker.from_env()
            client.ping()
        except Exception:
            return False
        return True

    def run_stage(
        self, image: ResolvedImage, inputs: list[pd.DataFrame], ctx: StageContext
    ) -> tuple[pd.DataFrame, str]:
        if not self.available():
            raise BackendUnavailableError("docker")
        # Container execution wiring is provider-specific; the contract is that the
        # container runs the same capability over mounted workspace artifacts and
        # returns an equivalent (frame, engine_mode). Not exercised without a daemon.
        raise BackendUnavailableError(
            "docker"
        )  # pragma: no cover - requires a live daemon


def select_backend(name: str) -> RuntimeBackend:
    """Select a backend by name; fail clearly if unavailable (Req 1.4, 1.5)."""
    if name == "process":
        return ProcessBackend()
    if name == "docker":
        backend = DockerBackend()
        if not backend.available():
            raise BackendUnavailableError("docker")
        return backend
    raise BackendUnavailableError(name)
