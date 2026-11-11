"""Model-output evaluation for prompt/context variants.

Unlike the structural prompt check, this module evaluates the text returned by
the configured model gateway. With no provider key it runs in explicit dry-run
mode, so the result is useful for wiring validation but not a production model
quality claim.
"""

from __future__ import annotations

import os
from typing import Any

from .gateway import ModelGateway
from .prompt_eval import CASES, PromptCase, render_prompt


def _provider_mode() -> str:
    provider = os.getenv("MODEL_PROVIDER", "openrouter")
    key_name = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }.get(provider, "")
    return "live_provider" if key_name and os.getenv(key_name) else "dry_run"


def score_model_response(case: PromptCase, response: str, *, variant: str) -> dict[str, Any]:
    text = response.lower()
    expected_hits = sum(term.lower() in text for term in case.expected_terms)
    forbidden_hits = sum(term.lower() in text for term in case.forbidden_terms)
    scope_explicit = variant != "baseline" and (
        f"property={case.property_slug}" in text
        or case.property_slug.lower() in text
        and ("only for" in text or "property" in text)
    )
    expected_coverage = expected_hits / max(len(case.expected_terms), 1)
    quality_score = 0.7 * expected_coverage + 0.2 * (1.0 if forbidden_hits == 0 else 0.0) + 0.1 * (1.0 if scope_explicit else 0.0)
    return {
        "property_slug": case.property_slug,
        "expected_term_hits": expected_hits,
        "expected_coverage": round(expected_coverage, 4),
        "forbidden_term_hits": forbidden_hits,
        "scope_explicit": scope_explicit,
        "quality_score": round(quality_score, 4),
        "passed": forbidden_hits == 0 and expected_coverage >= 0.66,
    }


async def evaluate_model_context(gateway: ModelGateway | None = None) -> dict[str, Any]:
    gateway = gateway or ModelGateway()
    variants = ("baseline", "tenant_scoped_v2")
    results: dict[str, list[dict[str, Any]]] = {variant: [] for variant in variants}
    for variant in variants:
        for case in CASES:
            response = await gateway.complete(
                messages=[
                    {"role": "system", "content": "Answer using only the supplied property context. Never invent availability or payment side effects."},
                    {"role": "user", "content": render_prompt(case, variant)},
                ],
                task="booking",
            )
            results[variant].append({"response_preview": str(response)[:500], **score_model_response(case, str(response), variant=variant)})
    summaries = {
        variant: round(sum(item["quality_score"] for item in items) / max(len(items), 1), 4)
        for variant, items in results.items()
    }
    return {
        "mode": _provider_mode(),
        "variants": list(variants),
        "mean_quality": summaries,
        "improvement": round(summaries["tenant_scoped_v2"] - summaries["baseline"], 4),
        "results": results,
    }
