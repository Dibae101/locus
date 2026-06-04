"""Locusfile loading, validation, and credential safety (Layer 2, Stage 2).

Loads YAML into a ``Locusfile`` model, validates it, and enforces the credential
guardrails: a raw provider key in the file is rejected, and the referenced ``.env``
must not be tracked by version control. ``init`` ensures ``.env`` is gitignored.

Requirements: 3.1, 3.6, 3.7, 4.1, 4.3, 4.4, 4.5.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from pydantic import ValidationError

from locus.errors import ConfigError, CredentialError
from locus.locusfile import Locusfile
from locus_engine.llm.credentials import looks_like_raw_key


def load_locusfile(path: str | Path) -> Locusfile:
    """Load and validate a Locusfile, then run credential-safety checks."""
    p = Path(path).expanduser()
    if not p.exists():
        raise ConfigError(f"Locusfile not found: {p}")
    try:
        data = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Locusfile must be a mapping, got {type(data).__name__}")

    try:
        lf = Locusfile.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(x) for x in first["loc"])
        raise ConfigError(f"invalid setting {loc!r}: {first['msg']}") from exc

    if not lf.image and not lf.pipeline:
        raise ConfigError("Locusfile must declare an 'image' or a 'pipeline'")
    if not lf.source and not any(s.source for s in lf.normalized_pipeline()):
        raise ConfigError("Locusfile must declare a 'source'")

    _check_credential_safety(lf, base_dir=p.parent)
    return lf


def _check_credential_safety(lf: Locusfile, *, base_dir: Path) -> None:
    # 1. No raw key literally in the llm config (Req 4.3).
    if lf.llm:
        for key, value in lf.llm.items():
            if isinstance(value, str) and looks_like_raw_key(value):
                raise CredentialError(
                    f"llm.{key} contains what looks like a raw API key; "
                    "use ${ENV_VAR} or an env_file reference instead"
                )
    # 2. A referenced .env must not be tracked by version control (Req 4.5).
    if lf.env_file:
        env_path = (base_dir / lf.env_file).resolve()
        if env_path.exists() and _is_git_tracked(env_path):
            raise CredentialError(
                f"{lf.env_file} is tracked by git; untrack it "
                f"(git rm --cached {lf.env_file}) to avoid committing secrets"
            )


def _is_git_tracked(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)],
            cwd=path.parent,
            capture_output=True,
            check=False,
        )
    except (OSError, FileNotFoundError):  # pragma: no cover - git absent
        return False
    return result.returncode == 0


def ensure_env_gitignored(project_dir: str | Path = ".") -> None:
    """On init, ensure '.env' is in .gitignore, creating it if absent (Req 4.4)."""
    d = Path(project_dir).expanduser()
    gitignore = d / ".gitignore"
    entries = []
    if gitignore.exists():
        entries = gitignore.read_text().splitlines()
    if ".env" not in [e.strip() for e in entries]:
        with gitignore.open("a") as f:
            if entries and entries[-1].strip():
                f.write("\n")
            f.write(".env\n")
