"""Claude Code (local CLI) backend. Same interface as the mock/Vertex clients.

Shells out to the installed `claude` CLI in headless mode (`claude -p`), so it
reuses your existing Claude Code login — no separate API key, SDK, or GCP needed.
The prompt and JSON parsing come from engine.llm.prompt, shared with Vertex.

    CLAUDE_CLI_MODEL    - model alias/id (default: haiku)
    CLAUDE_CLI_BIN      - path to the claude binary (default: claude on PATH)
    CLAUDE_CLI_TIMEOUT  - per-call timeout in seconds (default: 120)
"""

from __future__ import annotations

import os
import shutil
import subprocess

from engine.llm.base import PairContext, Verdict
from engine.llm.prompt import build_prompt, parse_verdict


class ClaudeCLIClient:
    """Implements the LLMClient protocol against the local `claude` CLI."""

    def __init__(self) -> None:
        self.bin = os.environ.get("CLAUDE_CLI_BIN", "claude")
        self.model = os.environ.get("CLAUDE_CLI_MODEL", "haiku")
        self.timeout = float(os.environ.get("CLAUDE_CLI_TIMEOUT", "120"))
        if shutil.which(self.bin) is None and not os.path.exists(self.bin):
            raise RuntimeError(
                f"claude CLI not found ({self.bin!r}). Install Claude Code, set "
                "CLAUDE_CLI_BIN, or use LLM_BACKEND=mock."
            )

    def classify(self, ctx: PairContext) -> Verdict:
        prompt = build_prompt(ctx)  # JSON contract lives here; do not change it
        raw = self._call_cli(prompt)
        return parse_verdict(raw, ctx)  # strips fences + re-validates with Pydantic

    def _call_cli(self, prompt: str) -> str:
        """Send `prompt` to the headless CLI and return the raw text response."""
        proc = subprocess.run(
            [
                self.bin,
                "-p",
                prompt,
                "--model",
                self.model,
                "--output-format",
                "text",
            ],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI failed (exit {proc.returncode}): "
                f"{proc.stderr.strip()[:500]}"
            )
        return proc.stdout
