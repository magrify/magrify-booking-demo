from __future__ import annotations

from typing import Any


def evaluate_workflow_state(state: dict[str, Any]) -> dict[str, Any]:
    """Deterministic safety/quality checks stored beside every agent run."""
    product = str(state.get("product", ""))
    payload = state.get("input") or {}
    checks: dict[str, bool] = {}
    if product == "magrify":
        checks["property_scoped"] = bool(str(payload.get("property_slug", "")).strip())
        checks["occupancy_valid"] = isinstance(payload.get("adults", 1), int) and payload.get("adults", 1) >= 1 and isinstance(payload.get("children", 0), int) and payload.get("children", 0) >= 0
        checks["availability_state_explicit"] = state.get("status") in {"available", "unavailable", "awaiting_configuration", "needs_information", "awaiting_approval", "payment_ready", "awaiting_payment", "confirmed", "recovery_due"}
        checks["no_unauthorized_refund"] = "refund" not in str(state.get("action", "")).lower()
    else:
        checks["tenant_scoped"] = bool(str(state.get("tenant_id", "")).strip())
        checks["icp_present"] = bool(str(payload.get("icp", "")).strip())
        checks["business_present"] = bool(str(payload.get("business_description", "")).strip())
        checks["approval_before_outreach"] = bool(state.get("approval_required", True)) or state.get("status") in {"awaiting_approval", "approved"}
        checks["no_unauthorized_outreach"] = state.get("action") not in {"send_outreach", "publish_content"} or not state.get("approval_required", True)
    passed = sum(checks.values())
    score = passed / max(len(checks), 1)
    return {"score": round(score, 4), "passed": score >= 0.75, "checks": checks}
