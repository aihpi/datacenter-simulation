"""Google Vertex AI backend. Same interface as the mock.

The Vertex/LLM SDK is imported lazily INSIDE the call so that selecting the mock
backend never requires the dependency or network. Configuration comes from
environment variables (see .env.example):

    VERTEX_PROJECT   - GCP project id
    VERTEX_LOCATION  - region, e.g. us-central1
    VERTEX_MODEL     - model id, e.g. gemini-2.5-pro
    GOOGLE_APPLICATION_CREDENTIALS - path to a service-account JSON (or use ADC)
"""

from __future__ import annotations

import os

from engine.llm.base import PairContext, Verdict
from engine.llm.prompt import build_prompt, parse_verdict


class VertexLLMClient:
    """Implements the LLMClient protocol against Vertex AI."""

    def __init__(self) -> None:
        self.project = os.environ.get("VERTEX_PROJECT")
        self.location = os.environ.get("VERTEX_LOCATION", "us-central1")
        self.model = os.environ.get("VERTEX_MODEL", "gemini-2.5-pro")
        self.temperature = float(os.environ.get("VERTEX_TEMPERATURE", "0.0"))
        if not self.project:
            raise RuntimeError(
                "VERTEX_PROJECT is not set. Configure Vertex env vars (see "
                ".env.example) or use LLM_BACKEND=mock."
            )

    def classify(self, ctx: PairContext) -> Verdict:
        prompt = build_prompt(ctx)  # template provided; do NOT change the JSON contract
        raw = self._call_vertex(prompt)
        return parse_verdict(raw, ctx)  # strips fences + re-validates with Pydantic

    def _call_vertex(self, prompt: str) -> str:
        """Send `prompt` to Vertex AI and return the raw text response.

        ====================================================================
        >>> PASTE YOUR WORKING VERTEX AI CALL HERE <<<
        It must send `prompt`, receive text, and return that text (a string).
        Use a LOW temperature (self.temperature, default 0.0). Keep the JSON
        contract from build_prompt() unchanged. Example skeleton (uncomment and
        adapt to your working call):

            from google import genai
            from google.genai import types

            client = genai.Client(
                vertexai=True, project=self.project, location=self.location
            )
            resp = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    response_mime_type="application/json",
                ),
            )
            return resp.text
        ====================================================================
        """
        raise NotImplementedError(
            "Vertex call not configured. Paste your working Vertex AI call into "
            "VertexLLMClient._call_vertex (engine/llm/vertex.py) and install the "
            "SDK, then run with LLM_BACKEND=vertex."
        )
