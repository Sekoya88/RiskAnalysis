"""Infrastructure — Google Gemini LLM adapter."""

from __future__ import annotations

import os
from typing import Any

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore[assignment,misc]


class GeminiLLMAdapter:
    """LLMPort implementation backed by Google Gemini API."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.1,
        max_output_tokens: int = 8192,
        api_key: str | None = None,
    ):
        if not ChatGoogleGenerativeAI:
            raise ImportError(
                "langchain-google-genai is not installed. "
                "Install with: pip install langchain-google-genai"
            )
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self._llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    async def ainvoke(self, messages: list[Any]) -> Any:
        return await self._llm.ainvoke(messages)

    def bind_tools(self, tools: list[Any]) -> GeminiLLMAdapter:
        adapter = GeminiLLMAdapter.__new__(GeminiLLMAdapter)
        adapter._llm = self._llm.bind_tools(tools)
        return adapter
