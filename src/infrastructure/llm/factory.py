"""Infrastructure — LLM Factory.

Creates the appropriate LLM adapter based on model name.
"""

from __future__ import annotations

import os
from typing import Any

from src.domain.ports.llm import LLMPort
from src.infrastructure.llm.ollama import OllamaLLMAdapter
from src.infrastructure.llm.google_genai import GeminiLLMAdapter


def create_llm(
    model: str | None = None,
    temperature: float | None = None,
    num_predict: int | None = None,
) -> Any:
    """Factory: create the right LLM adapter based on model name.

    Returns an object satisfying LLMPort (ainvoke + bind_tools).
    """
    model = model or os.getenv("OLLAMA_MODEL", "qwen3.5")

    if model.startswith("gemini"):
        return GeminiLLMAdapter(
            model=model,
            temperature=temperature if temperature is not None else 0.1,
            max_output_tokens=num_predict if num_predict is not None else 8192,
        )

    return OllamaLLMAdapter(
        model=model,
        temperature=temperature,
        num_predict=num_predict,
    )
