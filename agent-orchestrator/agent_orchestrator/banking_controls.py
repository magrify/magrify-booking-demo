"""Sandbox lender-package controls for banking-domain readiness.

This module models document completeness and exception routing only. It never
approves credit, sets a risk grade, or files a regulatory report.
"""

from __future__ import annotations

from typing import Any


REQUIRED_DOCUMENTS = ("rent_roll", "operating_statement", "inspection_report", "insurance")

CONTROL_OWNERS = {
    "document_completeness": "operations_analyst",
    "exception_review": "underwriter",
    "credit_decision": "human_credit_committee",
    "regulatory_review": "compliance_officer",
}


def review_lender_package(case: dict[str, Any]) -> dict[str, Any]:
    """Route a lender package to the right human review state."""
    supplied = {str(item).strip().lower() for item in (case.get("documents") or []) if str(item).strip()}
    missing = [document for document in REQUIRED_DOCUMENTS if document not in supplied]
    exceptions = [str(item).strip() for item in (case.get("exceptions") or []) if str(item).strip()]
    if missing:
        status = "needs_more_documents"
        next_step = "request_missing_documents"
    elif exceptions:
        status = "exception_review"
        next_step = "route_to_human_underwriter"
    else:
        status = "ready_for_credit_review"
        next_step = "route_to_human_credit_review"
    return {
        "case_id": str(case.get("case_id", "")),
        "property_id": str(case.get("property_id", "")),
        "status": status,
        "next_step": next_step,
        "missing_documents": missing,
        "exceptions": exceptions,
        "credit_decision": "not_made_by_agent",
        "regulatory_filing": "not_made_by_agent",
        "control_owners": CONTROL_OWNERS,
        "audit_event_required": True,
    }
