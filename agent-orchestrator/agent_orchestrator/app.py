from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .agents import framework_status
from .data_controls import validate_tenant_id
from .gateway import ModelGateway
from .store import Store
from .workflows import build_workflow
from .enrichment_worker import process_payload
from .evaluations import evaluate_workflow_state

try:
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except ImportError:  # optional in minimal installs; requirements includes it
    aiosqlite = None
    AsyncSqliteSaver = None

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / "openstays" / ".env.local")
except ImportError:
    pass


store = Store()
gateway = ModelGateway()
workflow = build_workflow(store, gateway)


async def run_persisted_workflow(state: dict, run_id: str) -> dict:
    """Run one graph invocation with a fresh async SQLite connection.

    The HTTP server is threaded and historically created a short-lived
    asyncio loop per request. Opening the checkpoint connection inside that
    same loop avoids cross-loop locks while retaining durable checkpoints.
    """
    if AsyncSqliteSaver is None or aiosqlite is None:
        return await workflow.ainvoke(state)
    async with aiosqlite.connect(os.getenv("AGENT_CHECKPOINT_PATH", "agent-orchestrator-checkpoints.sqlite3")) as connection:
        checkpointer = AsyncSqliteSaver(connection)
        await checkpointer.setup()
        graph = build_workflow(store, gateway, checkpointer=checkpointer)
        return await graph.ainvoke(state, config={"configurable": {"thread_id": run_id}})


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    expected = os.getenv("AGENT_ORCHESTRATOR_TOKEN")
    return not expected or handler.headers.get("Authorization") == f"Bearer {expected}"


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._json(200, {"ok": True, "service": "magrify-cartelbot-agent-orchestrator", "frameworks": framework_status()})
            return
        if not authorized(self):
            self._json(401, {"detail": "Unauthorized"})
            return
        if parsed.path.startswith("/v1/runs/"):
            run_id = parsed.path.rsplit("/", 1)[-1]
            if parsed.path.endswith("/observability"):
                run_id = parsed.path.split("/")[-2]
                run = store.get_run(run_id)
                self._json(200 if run else 404, {"run": run, "events": store.list_events(run_id), "evals": store.list_evals(run_id)} if run else {"detail": "Run not found"})
                return
            run = store.get_run(run_id)
            self._json(200 if run else 404, run or {"detail": "Run not found"})
            return
        if parsed.path == "/v1/knowledge/search":
            query = parse_qs(parsed.query)
            results = store.search_knowledge(query.get("tenant_id", [""])[0], query.get("namespace", [""])[0], query.get("q", [""])[0], int(query.get("limit", [5])[0]))
            self._json(200, {"results": results})
            return
        if parsed.path == "/v1/reports/nightly":
            query = parse_qs(parsed.query)
            tenant_id = query.get("tenant_id", ["magrify-default"])[0]
            validate_tenant_id(tenant_id)
            self._json(200, store.nightly_report(tenant_id))
            return
        self._json(404, {"detail": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not authorized(self):
            self._json(401, {"detail": "Unauthorized"})
            return
        parsed = urlparse(self.path)
        payload = self._body()
        if parsed.path == "/v1/livekit/booking":
            # LiveKit Agents can post the normalized call transcript/slots here.
            # The endpoint deliberately creates the same approval-gated run as
            # the website and CRM adapters; it never charges or confirms a stay.
            call_input = dict(payload.get("input", {}))
            call_input["channel"] = "phone"
            payload = {
                "product": "magrify",
                "workflow": "phone_concierge",
                "tenant_id": payload.get("tenant_id", "magrify-default"),
                "input": call_input,
                "require_approval": payload.get("require_approval", True),
            }
            parsed = urlparse("/v1/runs")
        if parsed.path == "/v1/livekit/knowledge":
            # Keep the orchestrator path compatible with the direct Convex
            # bridge: retrieval remains tenant-scoped and vectorless. A
            # property slug is included in the search terms so a tenant can
            # keep knowledge for multiple client properties in one store.
            tenant_id = str(payload.get("tenant_id", "magrify-default"))
            property_slug = str(payload.get("property_slug", "")).strip()
            question = str(payload.get("question", "")).strip()
            validate_tenant_id(tenant_id)
            if not property_slug or len(property_slug) > 120 or len(question) > 500:
                self._json(400, {"detail": "property_slug and a bounded question are required"})
                return
            results = store.search_knowledge(
                tenant_id,
                "property",
                f"{property_slug} {question}".strip(),
                8,
            )
            self._json(200, {"status": "knowledge", "property_slug": property_slug, "knowledge": results})
            return
        if parsed.path == "/v1/cartelbot/enrich":
            # This worker is deliberately separate from the prospector graph:
            # enrichment can be slow, bounded, retried, or moved to a queue
            # without changing the Cloudflare Worker approval surface.
            tenant_id = str(payload.get("tenant_id", ""))
            validate_tenant_id(tenant_id)
            try:
                result = process_payload(payload)
            except ValueError as error:
                self._json(400, {"detail": str(error)})
                return
            self._json(200, {"tenant_id": tenant_id, **result})
            return
        if parsed.path == "/v1/runs":
            validate_tenant_id(str(payload["tenant_id"]))
            run_id = store.create_run(product=payload["product"], workflow=payload["workflow"], tenant_id=payload["tenant_id"], payload=payload.get("input", {}), approval_required=payload.get("require_approval", True))
            store.event(run_id, "run_started", {"product": payload["product"], "workflow": payload["workflow"]})
            try:
                state = None
                last_error: Exception | None = None
                for attempt in range(1, 4):
                    try:
                        state = asyncio.run(run_persisted_workflow(
                            {"product": payload["product"], "workflow": payload["workflow"], "tenant_id": payload["tenant_id"], "input": payload.get("input", {}), "approval_required": payload.get("require_approval", True)},
                            run_id,
                        ))
                        store.event(run_id, "run_attempt_succeeded", {"attempt": attempt})
                        break
                    except Exception as error:  # retry transient provider/workflow failures
                        last_error = error
                        store.event(run_id, "run_attempt_failed", {"attempt": attempt, "error": type(error).__name__})
                if state is None:
                    raise last_error or RuntimeError("workflow failed")
            except Exception as error:
                store.finish_run(run_id, status="failed", output={"error": type(error).__name__})
                self._json(502, {"run_id": run_id, "status": "failed", "detail": "Agent workflow failed after retries"})
                return
            output = {"qualification": state.get("qualification"), "discovery": state.get("discovery"), "enrichment": state.get("enrichment"), "research_output": state.get("research_output"), "fit_score": state.get("fit_score"), "approval": state.get("approval"), "reply_classification": state.get("reply_classification"), "meeting": state.get("meeting"), "revenue": state.get("revenue"), "draft": state.get("draft"), "context": state.get("context", []), "status": state.get("status"), "runtime": state.get("runtime")}
            evaluation = evaluate_workflow_state(state)
            store.add_eval(run_id, "deterministic_safety", evaluation["score"], evaluation["passed"], json.dumps(evaluation["checks"], sort_keys=True))
            store.event(run_id, "agent_eval", evaluation)
            output["evaluation"] = evaluation
            store.finish_run(run_id, status=str(state.get("status", "completed")), output=output)
            store.event(run_id, "run_completed", {"status": state.get("status"), "context_count": len(state.get("context", []))})
            self._json(200, {"run_id": run_id, **output})
            return
        if parsed.path.startswith("/v1/runs/") and parsed.path.endswith("/approval"):
            run_id = parsed.path.split("/")[-2]
            approved = bool(payload.get("approved"))
            ok = store.approve(run_id, approved=approved, actor_id=str(payload.get("actor_id", "unknown")), reason=payload.get("reason"))
            if not ok:
                self._json(404, {"detail": "Run not found"})
                return
            if approved:
                run = store.get_run(run_id)
                try:
                    if run:
                        state = asyncio.run(run_persisted_workflow({
                            "product": run["product"],
                            "workflow": run["workflow"],
                            "tenant_id": run["tenant_id"],
                            "input": run["input"],
                            "approval_required": False,
                        }, run_id))
                        output = {"qualification": state.get("qualification"), "discovery": state.get("discovery"), "enrichment": state.get("enrichment"), "research_output": state.get("research_output"), "fit_score": state.get("fit_score"), "approval": state.get("approval"), "reply_classification": state.get("reply_classification"), "meeting": state.get("meeting"), "revenue": state.get("revenue"), "draft": state.get("draft"), "context": state.get("context", []), "status": state.get("status"), "runtime": state.get("runtime"), "action": state.get("action"), "availability": state.get("availability"), "hold": state.get("hold"), "payment": state.get("payment")}
                        evaluation = evaluate_workflow_state(state)
                        store.add_eval(run_id, "deterministic_safety", evaluation["score"], evaluation["passed"], json.dumps(evaluation["checks"], sort_keys=True))
                        store.event(run_id, "agent_eval", evaluation)
                        output["evaluation"] = evaluation
                        store.finish_run(run_id, status=str(state.get("status", "approved")), output=output)
                        store.event(run_id, "approval_resumed", {"status": state.get("status"), "action": state.get("action")})
                        self._json(200, {"run_id": run_id, "approval_status": "approved", "status": state.get("status"), "action": state.get("action"), "output": output})
                        return
                except Exception as error:
                    store.finish_run(run_id, status="failed", output={"error": type(error).__name__})
                    self._json(502, {"run_id": run_id, "approval_status": "approved", "status": "failed", "detail": "Approved workflow failed"})
                    return
            self._json(200, {"run_id": run_id, "approval_status": "rejected"})
            return
        if parsed.path == "/v1/evals":
            try:
                eval_id = store.add_eval(str(payload["run_id"]), str(payload.get("evaluator", "default")), float(payload["score"]), bool(payload["passed"]), payload.get("notes"))
            except KeyError:
                self._json(404, {"detail": "Run not found"})
                return
            self._json(200, {"eval_id": eval_id, "run_id": payload["run_id"]})
            return
        if parsed.path == "/v1/knowledge":
            doc_id = store.add_knowledge(str(payload["tenant_id"]), str(payload["namespace"]), str(payload["title"]), str(payload["content"]), list(payload.get("tags", [])))
            self._json(200, {"id": doc_id})
            return
        self._json(404, {"detail": "Not found"})


def main() -> None:
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8788
    server = ThreadingHTTPServer((os.getenv("HOST", "127.0.0.1"), port), Handler)
    print(f"agent orchestrator listening on http://{server.server_address[0]}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
