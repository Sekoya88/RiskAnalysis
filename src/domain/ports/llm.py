"""Port — LLM abstraction (Protocol)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMPort(Protocol):
    """Abstract interface for LLM providers.

    Implementations: OllamaLLMAdapter, GeminiLLMAdapter.
    """

    async def ainvoke(self, messages: list[Any]) -> Any:
        """Invoke the LLM asynchronously."""
        ...

    def bind_tools(self, tools: list[Any]) -> LLMPort:
        """Return a new LLM instance with tools bound."""
        ...
