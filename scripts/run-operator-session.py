"""Drive a repeatable operator rehearsal through the public HTTP workflow."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from pathlib import Path
import sys


def call(base_url: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(f"{base_url.rstrip('/')}{path}", data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


base_url = os.getenv("AGENT_ORCHESTRATOR_URL", "http://127.0.0.1:8788")
tenant_id = os.getenv("OPERATOR_REHEARSAL_TENANT", "cartelbot:operator-rehearsal")
started_at = datetime.now(timezone.utc).isoformat()

cartelbot = call(base_url, "POST", "/v1/runs", {
    "product": "cartelbot",
    "workflow": "prospector",
    "tenant_id": tenant_id,
    "require_approval": True,
    "input": {
        "business_description": "booking and operations software for independent campgrounds",
        "icp": "campground operators with direct-booking websites",
        "offer": "reduce abandoned inquiries with a voice and chat concierge",
        "message": "Find qualified buyers and prepare a first outreach draft",
        "leads": [{"name": "Demo Operator", "company": "Example Campground", "website": "https://example.com"}],
    },
})
run_id = cartelbot["run_id"]
approved = call(base_url, "POST", f"/v1/runs/{run_id}/approval", {
    "approved": True,
    "actor_id": "operator-rehearsal",
    "reason": "Reviewed fit score and approved draft preparation",
})

adoption_events = [
    ("operator_feedback", "Operator asked for one inbox from inquiry through approval."),
    ("demo_presented", "Prospector pipeline and booking handoff demonstrated."),
    ("deployment_configured", "Tenant, ICP, offer, and approval policy configured."),
    ("staff_training_completed", "Operator rehearsal completed with the handoff path."),
    ("staff_workflow_used", "Rehearsal changed the operator workflow from manual triage to an approval queue with recovery visibility."),
]
for event_name, note in adoption_events:
    call(base_url, "POST", "/v1/monitoring/adoption/events", {
        "tenant_id": tenant_id,
        "event": event_name,
        "actor_role": "operator",
        "metadata": {"mode": "operator_rehearsal", "note": note},
    })

adoption = call(base_url, "GET", f"/v1/monitoring/adoption?tenant_id={tenant_id}")
reliability = call(base_url, "GET", f"/v1/monitoring/reliability?tenant_id={tenant_id}")

print(json.dumps({
    "mode": "operator_rehearsal",
    "started_at": started_at,
    "tenant_id": tenant_id,
    "journey": {
        "run_id": run_id,
        "before_approval": {"status": cartelbot.get("status"), "action": cartelbot.get("action")},
        "after_approval": {"status": approved.get("status"), "action": approved.get("action")},
    },
    "adoption": adoption,
    "reliability": reliability,
    "workflow_change": "Manual inquiry triage becomes a tenant-scoped approval queue with a visible recovery path and recorded staff handoff.",
    "evidence_boundary": "Local operator rehearsal; not a claim of customer sign-off or production adoption.",
}, indent=2))
