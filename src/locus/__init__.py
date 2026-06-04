"""Locus CLI — Layer 2.

The image runtime, packaging, distribution, and registry client built on top of the
Layer 1 engine (``locus_engine``). Provides the ``locus`` command: pull, run, build,
push, search.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("locus-etl")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
