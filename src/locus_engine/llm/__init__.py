"""Optional LLM engine, provider routing, and local credential handling.

Everything in this package is OFF by default. The LLM engine activates only when a
local credential is present (a presence check that makes no network call). No
credential or user data is ever transmitted to any hosted Locus service.
"""

from __future__ import annotations

from locus_engine.llm.credentials import CredentialResolver
from locus_engine.llm.router import ProviderRouter

__all__ = ["CredentialResolver", "ProviderRouter"]
