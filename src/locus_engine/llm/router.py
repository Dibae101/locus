"""Provider router (Stage 6.2) — in-process LiteLLM wrapper.

Maps ``provider`` + ``model`` to a single in-process completion call via the LiteLLM
SDK. It never spawns or requires a separate proxy server (Req 15.7). LiteLLM is an
optional dependency, imported lazily, so the core engine stays lightweight and the
no-LLM path has zero LLM dependencies.

Requirements: 15.6, 15.7.
"""

from __future__ import annotations

from typing import Any, Protocol


class CompletionFn(Protocol):
    def __call__(self, *, model: str, messages: list[dict[str, str]], **kwargs: Any) -> Any: ...


class ProviderRouter:
    """Routes a completion request to the configured provider/model in-process."""

    def __init__(self, completion_fn: CompletionFn | None = None) -> None:
        # Injectable for tests; defaults to LiteLLM when first used.
        self._completion_fn = completion_fn

    def _fn(self) -> CompletionFn:
        if self._completion_fn is not None:
            return self._completion_fn
        try:
            import litellm
        except ImportError as exc:  # pragma: no cover - exercised when extra missing
            raise RuntimeError(
                "LLM features require the 'llm' extra: pip install locus-engine[llm]"
            ) from exc
        self._completion_fn = litellm.completion
        return self._completion_fn

    def model_string(self, provider: str, model: str) -> str:
        return f"{provider}/{model}"

    def complete(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        api_key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        fn = self._fn()
        return fn(
            model=self.model_string(provider, model),
            messages=messages,
            api_key=api_key,
            **kwargs,
        )
