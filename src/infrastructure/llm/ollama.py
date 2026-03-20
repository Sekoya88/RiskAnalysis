"""Infrastructure — Ollama LLM adapter."""

from __future__ import annotations

import os
from typing import Any

from langchain_ollama import ChatOllama

from src.infrastructure.config.providers import get_model_config


class OllamaLLMAdapter:
    """LLMPort implementation backed by Ollama (local inference)."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        num_predict: int | None = None,
        base_url: str | None = None,
    ):
        model = model or os.getenv("OLLAMA_MODEL", "qwen3.5")
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        cfg = get_model_config(model)

        self._llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature if temperature is not None else cfg.get("temperature", 0.1),
            num_predict=num_predict if num_predict is not None else cfg.get("num_predict", 4096),
        )

    async def ainvoke(self, messages: list[Any]) -> Any:
        return await self._llm.ainvoke(messages)

    def bind_tools(self, tools: list[Any]) -> OllamaLLMAdapter:
        """Return a wrapper with tools bound to the underlying LLM."""
        adapter = OllamaLLMAdapter.__new__(OllamaLLMAdapter)
        adapter._llm = self._llm.bind_tools(tools)
        return adapter
