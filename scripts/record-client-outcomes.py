"""Record owner-supplied client sign-off/adoption milestones."""

from __future__ import annotations

import json
import os
from urllib.parse import quote
from urllib.request import Request, urlopen


base_url = os.getenv("AGENT_ORCHESTRATOR_URL", "http://127.0.0.1:8788").rstrip("/")
clients = (
    ("client:aguasdeibiza", "aguasdeibiza.com", "hospitality/resort guest experience"),
    ("client:bancalsf", "bancalsf.com", "property-management inquiry experience"),
)


def post(payload: dict) -> None:
    request = Request(
        f"{base_url}/v1/monitoring/adoption/events",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=30):
        return


for tenant_id, domain, engagement in clients:
    for event_name in ("client_signoff", "client_adoption_observed"):
        post({
            "tenant_id": tenant_id,
            "event": event_name,
            "actor_role": "client_owner_reported",
            "metadata": {
                "domain": domain,
                "engagement": engagement,
                "source": "magrify_owner_report",
                "evidence_boundary": "No unverified traffic or revenue metric asserted",
            },
        })

    with urlopen(f"{base_url}/v1/monitoring/adoption?tenant_id={quote(tenant_id)}", timeout=30) as response:
        report = json.loads(response.read().decode("utf-8"))
    print(json.dumps({"tenant_id": tenant_id, "domain": domain, "report": report}, indent=2))
