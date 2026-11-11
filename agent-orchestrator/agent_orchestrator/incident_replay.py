"""Replay a stalled-approval incident through the production event schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import Store


def replay_stalled_approval(path: str | Path, *, tenant_id: str = "property:incident-replay") -> dict[str, Any]:
    """Create, detect, recover, and verify one approval incident in SQLite."""
    store = Store(str(path))
    run_id = store.create_run(
        product="magrify",
        workflow="phone_concierge",
        tenant_id=tenant_id,
        payload={"property_slug": "incident-replay", "message": "test stalled approval"},
        approval_required=True,
    )
    store.event(run_id, "run_started", {"source": "incident_replay"})
    store.finish_run(run_id, status="awaiting_approval", output={"status": "awaiting_approval"})
    store.event(run_id, "workflow_state", {"status": "awaiting_approval", "action": "approve_temporary_hold"})
    detected = store.get_run(run_id)
    store.approve(run_id, approved=True, actor_id="incident-replay-operator", reason="resume saved booking checkpoint")
    store.event(run_id, "approval_resumed", {"status": "confirmed", "action": "send_confirmation"})
    store.finish_run(run_id, status="confirmed", output={"status": "confirmed", "recovered_from": "awaiting_approval"})
    recovered = store.get_run(run_id)
    return {
        "mode": "incident_replay",
        "run_id": run_id,
        "detected_status": detected["status"] if detected else None,
        "recovered_status": recovered["status"] if recovered else None,
        "events": [event["name"] for event in store.list_events(run_id)],
        "verified": bool(detected and detected["status"] == "awaiting_approval" and recovered and recovered["status"] == "confirmed"),
    }
