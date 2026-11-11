"""Synthetic traffic harness for the reliability ledger.

The harness is intentionally separate from production endpoints. It exercises
the same Store event schema with concurrent validation traffic so operators can
prove the monitoring math before exposing a deployment to real guests.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .store import Store


def _record_validation_run(store: Store, tenant_id: str, index: int) -> str:
    run_id = store.create_run(
        product="magrify",
        workflow="phone_concierge",
        tenant_id=tenant_id,
        payload={"property_slug": "load-test", "message": f"validation run {index}"},
        approval_required=True,
    )
    store.event(run_id, "run_started", {"source": "synthetic_load_test", "index": index})
    store.event(run_id, "run_attempt_succeeded", {"attempt": 1})
    if index % 10 == 0:
        store.finish_run(run_id, status="failed", output={"status": "failed", "source": "synthetic_load_test"})
        store.event(run_id, "workflow_state", {"status": "failed", "action": "handoff_to_staff"})
    elif index % 7 == 0:
        store.finish_run(run_id, status="awaiting_approval", output={"status": "awaiting_approval", "source": "synthetic_load_test"})
        store.event(run_id, "workflow_state", {"status": "awaiting_approval", "action": "approve_temporary_hold"})
    else:
        store.event(run_id, "approval_decision", {"approved": True, "source": "synthetic_load_test"})
        store.event(run_id, "approval_resumed", {"status": "confirmed"})
        store.finish_run(run_id, status="confirmed", output={"status": "confirmed", "source": "synthetic_load_test"})
        store.event(run_id, "workflow_state", {"status": "confirmed", "action": "send_confirmation"})
    return run_id


def run_validation_load(path: str | Path, *, tenant_id: str = "property:load-test", runs: int = 100) -> dict[str, Any]:
    """Run bounded concurrent validation traffic and return the real ledger report."""
    bounded_runs = min(max(int(runs), 1), 5000)
    store = Store(str(path))
    with ThreadPoolExecutor(max_workers=min(16, bounded_runs)) as pool:
        list(pool.map(lambda index: _record_validation_run(store, tenant_id, index), range(1, bounded_runs + 1)))
    report = store.reliability_report(tenant_id, window_hours=24)
    return {"mode": "validation_run", "runs_requested": bounded_runs, "report": report}
