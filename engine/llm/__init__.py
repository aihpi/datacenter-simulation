"""LLM backend selection. `LLM_BACKEND` env var picks the implementation
('mock' default, 'vertex'). The Vertex SDK is only imported when selected."""

from __future__ import annotations

import os

from engine.llm.base import (
    ColumnInfo,
    CorrelationStat,
    LLMClient,
    PairContext,
    Verdict,
    VerdictLabel,
)

__all__ = [
    "ColumnInfo",
    "CorrelationStat",
    "LLMClient",
    "PairContext",
    "Verdict",
    "VerdictLabel",
    "get_client",
]


def get_client(backend: str | None = None) -> LLMClient:
    """Return an LLMClient for the selected backend (default from LLM_BACKEND)."""
    backend = (backend or os.environ.get("LLM_BACKEND", "mock")).lower()
    if backend == "mock":
        from engine.llm.mock import MockLLMClient

        return MockLLMClient()
    if backend == "vertex":
        from engine.llm.vertex import VertexLLMClient

        return VertexLLMClient()
    if backend in ("claude_cli", "claude"):
        from engine.llm.claude_cli import ClaudeCLIClient

        return ClaudeCLIClient()
    raise ValueError(
        f"Unknown LLM_BACKEND={backend!r}. Use 'mock', 'vertex', or 'claude_cli'."
    )
