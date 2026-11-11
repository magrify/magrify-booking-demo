from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .data_controls import redact


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.getenv("AGENT_STORE_PATH", "agent-orchestrator.sqlite3")
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY,
                  product TEXT NOT NULL,
                  workflow TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  input_json TEXT NOT NULL,
                  output_json TEXT,
                  approval_required INTEGER NOT NULL,
                  approval_status TEXT NOT NULL DEFAULT 'pending',
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS runs_tenant ON runs(tenant_id, created_at);
                CREATE TABLE IF NOT EXISTS events (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_run ON events(run_id, created_at);
                CREATE TABLE IF NOT EXISTS evals (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  evaluator TEXT NOT NULL,
                  score REAL NOT NULL,
                  passed INTEGER NOT NULL,
                  notes TEXT,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge (
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  namespace TEXT NOT NULL,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  tags_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS knowledge_tenant ON knowledge(tenant_id, namespace);
                """
            )

    def create_run(self, *, product: str, workflow: str, tenant_id: str, payload: dict[str, Any], approval_required: bool) -> str:
        run_id = f"run_{uuid.uuid4().hex}"
        now = utc_now()
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO runs(id, product, workflow, tenant_id, status, input_json, approval_required, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, product, workflow, tenant_id, "running", json.dumps(redact(payload)), int(approval_required), now, now),
            )
        return run_id

    def finish_run(self, run_id: str, *, status: str, output: dict[str, Any]) -> None:
        with self._lock, self._connect() as db:
            db.execute("UPDATE runs SET status=?, output_json=?, updated_at=? WHERE id=?", (status, json.dumps(output), utc_now(), run_id))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["input"] = json.loads(result.pop("input_json"))
        result["output"] = json.loads(result.pop("output_json")) if result.get("output_json") else None
        result.pop("output_json", None)
        return result

    def approve(self, run_id: str, *, approved: bool, actor_id: str, reason: str | None) -> bool:
        status = "approved" if approved else "rejected"
        with self._lock, self._connect() as db:
            result = db.execute("UPDATE runs SET approval_status=?, status=?, updated_at=? WHERE id=?", (status, "approved" if approved else "rejected", utc_now(), run_id))
            if not result.rowcount:
                return False
        self.event(run_id, "approval_decision", {"approved": approved, "actor_id": actor_id, "reason": reason})
        return True

    def event(self, run_id: str, name: str, payload: dict[str, Any]) -> None:
        run = self.get_run(run_id)
        if not run:
            return
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO events(id, run_id, tenant_id, name, payload_json, created_at) VALUES(?,?,?,?,?,?)", (f"evt_{uuid.uuid4().hex}", run_id, run["tenant_id"], name, json.dumps(redact(payload)), utc_now()))

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id, name, payload_json, created_at FROM events WHERE run_id=? ORDER BY created_at", (run_id,)).fetchall()
        return [{"id": row["id"], "name": row["name"], "payload": json.loads(row["payload_json"]), "created_at": row["created_at"]} for row in rows]

    def add_eval(self, run_id: str, evaluator: str, score: float, passed: bool, notes: str | None) -> str:
        eval_id = f"eval_{uuid.uuid4().hex}"
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO evals(id, run_id, evaluator, score, passed, notes, created_at) VALUES(?,?,?,?,?,?,?)", (eval_id, run_id, evaluator, score, int(passed), notes, utc_now()))
        return eval_id

    def list_evals(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id, evaluator, score, passed, notes, created_at FROM evals WHERE run_id=? ORDER BY created_at", (run_id,)).fetchall()
        return [dict(row) for row in rows]

    def nightly_report(self, tenant_id: str) -> dict[str, Any]:
        """Build a small durable occupancy/revenue-style operations report.

        The report reads redacted run outputs and never sits on the booking
        critical path. It is useful for a nightly job or an operator dashboard
        without introducing a second source of truth.
        """
        with self._connect() as db:
            rows = db.execute(
                "SELECT status, output_json, created_at FROM runs WHERE tenant_id=? AND created_at >= datetime('now', '-1 day') ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
        totals = {"runs": len(rows), "confirmed": 0, "recovery_due": 0, "failed": 0, "revenue_cents": 0}
        for row in rows:
            status = str(row["status"])
            if status == "confirmed":
                totals["confirmed"] += 1
            elif status == "recovery_due":
                totals["recovery_due"] += 1
            elif status == "failed":
                totals["failed"] += 1
            try:
                output = json.loads(row["output_json"] or "{}")
            except json.JSONDecodeError:
                output = {}
            revenue = output.get("revenue") or {}
            if isinstance(revenue, dict) and isinstance(revenue.get("amount_cents"), (int, float)):
                totals["revenue_cents"] += int(revenue["amount_cents"])
        return {"tenant_id": tenant_id, "window": "24h", **totals}

    def add_knowledge(self, tenant_id: str, namespace: str, title: str, content: str, tags: list[str]) -> str:
        doc_id = f"doc_{uuid.uuid4().hex}"
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO knowledge(id, tenant_id, namespace, title, content, tags_json, created_at) VALUES(?,?,?,?,?,?,?)", (doc_id, tenant_id, namespace, title, content, json.dumps(tags), utc_now()))
        return doc_id

    def search_knowledge(self, tenant_id: str, namespace: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        terms = [term.lower() for term in query.split() if len(term) > 2]
        with self._connect() as db:
            rows = db.execute("SELECT * FROM knowledge WHERE tenant_id=? AND namespace=? ORDER BY created_at DESC", (tenant_id, namespace)).fetchall()
        scored: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            haystack = f"{row['title']} {row['content']} {row['tags_json']}".lower()
            scored.append((sum(1 for term in terms if term in haystack), row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [{"id": row["id"], "title": row["title"], "content": row["content"], "tags": json.loads(row["tags_json"]), "score": score} for score, row in scored[:limit] if score > 0]
