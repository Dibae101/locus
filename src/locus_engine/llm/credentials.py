"""Local-only LLM credential resolution (Stage 6.1).

Resolves an LLM provider key at run time from local sources only, in precedence
order: a referenced ``.env`` file, an environment variable, then the OS keyring.
The resolver only performs a presence check to drive engine activation; it never
transmits the key anywhere (Req 15.2). A raw key literally embedded in config is
rejected (Req 15.3).

Requirements: 15.1, 15.2, 15.3; Property 7 (no egress without a credential).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from locus_engine.errors import ConfigError

# Conservative patterns for "this looks like a real secret key" detection.
_RAW_KEY_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
)

# Default env var names per provider.
_PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure": "AZURE_API_KEY",
    "google": "GEMINI_API_KEY",
    "ollama": "OLLAMA_API_KEY",  # often unused; local models may need no key
}


def looks_like_raw_key(value: str) -> bool:
    return any(p.search(value) for p in _RAW_KEY_PATTERNS)


def assert_no_raw_key_in_config(value: str | None, *, setting: str = "llm.api_key") -> None:
    """Reject a raw key literally present in config (Req 15.3)."""
    if value and looks_like_raw_key(value):
        raise ConfigError(
            f"setting {setting!r} contains what looks like a raw API key; "
            "use an environment reference (e.g. ${OPENAI_API_KEY}) or a .env file instead"
        )


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


class CredentialResolver:
    """Resolves an LLM credential from local sources only."""

    def __init__(self, env_file: str | None = None) -> None:
        self._env_file = env_file
        self._env_file_cache: dict[str, str] | None = None

    def _env_file_values(self) -> dict[str, str]:
        if self._env_file_cache is None:
            path = Path(self._env_file).expanduser() if self._env_file else None
            self._env_file_cache = (
                _parse_env_file(path) if path and path.exists() else {}
            )
        return self._env_file_cache

    def resolve(self, provider: str) -> str | None:
        """Return the key for ``provider`` from local sources, or None.

        Precedence: .env file -> environment variable -> OS keyring.
        Never makes a network call.
        """
        env_name = _PROVIDER_ENV.get(provider, f"{provider.upper()}_API_KEY")

        # 1. .env file
        from_file = self._env_file_values().get(env_name)
        if from_file:
            return from_file

        # 2. environment variable
        from_env = os.environ.get(env_name)
        if from_env:
            return from_env

        # 3. OS keyring (optional dependency; absence is not an error)
        return self._from_keyring(provider)

    def is_available(self, provider: str) -> bool:
        """Presence check only (Req 13.4) — no network, no key returned."""
        return self.resolve(provider) is not None

    @staticmethod
    def _from_keyring(provider: str) -> str | None:
        try:
            import keyring
        except ImportError:
            return None
        try:
            result = keyring.get_password("locus", provider)
        except Exception:  # pragma: no cover - keyring backend issues
            return None
        return result if isinstance(result, str) else None
