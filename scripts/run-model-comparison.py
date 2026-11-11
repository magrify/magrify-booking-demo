"""Run a bounded provider comparison on the booking context cases.

The script is intentionally small and paid-call bounded: two models, two
fixed property-scoped cases, and a low output-token cap. It records model IDs,
latency, token usage, and the same rubric used by the model evaluator without
printing credentials.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-orchestrator"))

from agent_orchestrator.model_eval import score_model_response
from agent_orchestrator.prompt_eval import CASES, render_prompt


def _max_tokens() -> int:
    try:
        return max(64, min(int(os.getenv("MODEL_COMPARISON_MAX_TOKENS", "96")), 256))
    except ValueError:
        return 96


async def _run_model(client: Any, model: str) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in CASES:
        started = time.perf_counter()
        response = await client.messages.create(
            model=model,
            max_tokens=_max_tokens(),
            system="Answer using only the supplied property context. Never invent availability or payment side effects.",
            messages=[{"role": "user", "content": render_prompt(case, "tenant_scoped_v2")}],
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        cases.append(
            {
                "property_slug": case.property_slug,
                "latency_ms": latency_ms,
                "input_tokens": getattr(response.usage, "input_tokens", None),
                "output_tokens": getattr(response.usage, "output_tokens", None),
                "rubric": score_model_response(case, text, variant="tenant_scoped_v2"),
                "response_preview": text[:240],
            }
        )
    quality = [item["rubric"]["quality_score"] for item in cases]
    return {
        "model": model,
        "mean_quality": round(sum(quality) / len(quality), 4),
        "mean_latency_ms": round(sum(item["latency_ms"] for item in cases) / len(cases), 1),
        "total_input_tokens": sum(item["input_tokens"] or 0 for item in cases),
        "total_output_tokens": sum(item["output_tokens"] or 0 for item in cases),
        "cases": cases,
    }


async def main() -> None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is required for the paid comparison")
    from anthropic import AsyncAnthropic

    cheap = os.getenv("MODEL_COMPARISON_CHEAP", "claude-haiku-4-5-20251001")
    strong = os.getenv("MODEL_COMPARISON_STRONG", "claude-sonnet-4-5-20250929")
    client = AsyncAnthropic(api_key=key)
    results = [await _run_model(client, model) for model in (cheap, strong)]
    print(json.dumps({"mode": "live_provider_comparison", "rubric": "model_eval.score_model_response", "results": results}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
