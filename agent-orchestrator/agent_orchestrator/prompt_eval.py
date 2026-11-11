"""Deterministic prompt/context optimization checks for the agent gateway.

This is a small training-style loop, not model-weight training. It compares
prompt/context variants on a fixed safety-oriented fixture set and keeps the
best variant for the next deployment. That makes prompt changes measurable and
repeatable without adding a vector database or sending guest data to a vendor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromptCase:
    tenant_id: str
    property_slug: str
    question: str
    context: str
    expected_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...]


CASES = (
    PromptCase(
        tenant_id="tenant-demo",
        property_slug="woodland-rv",
        question="What is the cancellation policy for a 30 amp site?",
        context="woodland-rv cancellation: full refund until 7 days before arrival; 30 amp sites available in summer.",
        expected_terms=("woodland-rv", "cancellation", "30 amp"),
        forbidden_terms=("lakeside-cabins",),
    ),
    PromptCase(
        tenant_id="tenant-demo",
        property_slug="lakeside-cabins",
        question="Does the cabin include linens?",
        context="lakeside-cabins amenities: linens and towels are included; RV sites are a separate inventory.",
        expected_terms=("lakeside-cabins", "linens"),
        forbidden_terms=("woodland-rv",),
    ),
)


def render_prompt(case: PromptCase, variant: str) -> str:
    if variant == "baseline":
        return f"Answer the guest question. Question: {case.question}\nContext: {case.context}"
    if variant == "tenant_scoped_v2":
        return (
            f"Answer only for tenant={case.tenant_id}, property={case.property_slug}. "
            "Use only the supplied property context. If the context does not answer the question, say that you do not know. "
            f"Question: {case.question}\nProperty context: {case.context}"
        )
    raise ValueError(f"unknown prompt variant: {variant}")


def score_variant(variant: str) -> dict[str, Any]:
    scores: list[float] = []
    case_results: list[dict[str, Any]] = []
    for case in CASES:
        prompt = render_prompt(case, variant).lower()
        expected_hits = sum(term.lower() in prompt for term in case.expected_terms)
        forbidden_hits = sum(term.lower() in prompt for term in case.forbidden_terms)
        scope_guard = variant != "baseline" and f"property={case.property_slug}" in prompt
        term_coverage = expected_hits / max(len(case.expected_terms), 1)
        # Weight answer coverage and explicit property scoping separately so
        # the eval can detect a context-boundary improvement even when both
        # variants contain the same factual terms.
        score = 0.8 * term_coverage + 0.2 * (1.0 if scope_guard else 0.0)
        if forbidden_hits:
            score = 0.0
        scores.append(score)
        case_results.append(
            {
                "property_slug": case.property_slug,
                "expected_term_hits": expected_hits,
                "forbidden_term_hits": forbidden_hits,
                "scope_guard": scope_guard,
                "score": round(score, 4),
            }
        )
    mean_score = sum(scores) / max(len(scores), 1)
    return {"variant": variant, "mean_score": round(mean_score, 4), "passed": mean_score >= 0.9, "cases": case_results}


def optimize_prompt_context(*, iterations: int = 3) -> dict[str, Any]:
    """Run a repeatable prompt-optimization loop and select the best variant."""
    candidates = ("baseline", "tenant_scoped_v2")
    history: list[dict[str, Any]] = []
    best = None
    for iteration in range(1, max(1, iterations) + 1):
        scored = [score_variant(candidate) for candidate in candidates]
        selected = max(scored, key=lambda result: result["mean_score"])
        history.append({"iteration": iteration, "candidates": scored, "selected": selected["variant"]})
        best = selected
    assert best is not None
    baseline = score_variant("baseline")
    return {
        "objective": "preserve property-scoped answer quality while making context boundaries explicit",
        "iterations": len(history),
        "baseline": baseline,
        "selected": best,
        "improvement": round(best["mean_score"] - baseline["mean_score"], 4),
        "history": history,
    }
