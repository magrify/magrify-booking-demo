"""Read-only tools used by the optional Deep Agents research pass."""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.tools import tool

from .search_adapters import file_search


@tool
def search_workspace_files(query: str) -> str:
    """Search bounded tenant research files; never writes or sends messages."""
    root = os.getenv("AGENT_FILE_SEARCH_ROOT")
    tenant_id = os.getenv("DEEPAGENTS_TENANT_ID", "cartelbot:research")
    if not root:
        return "File search is not configured."
    return json.dumps(file_search(root, tenant_id, query, limit=8))


@tool
def inspect_lead_record(record_json: str) -> str:
    """Summarize a lead record for research without contacting the lead."""
    try:
        record: dict[str, Any] = json.loads(record_json)
    except json.JSONDecodeError:
        return "Invalid lead JSON."
    allowed = {key: record.get(key) for key in ("name", "company", "website", "industry", "title") if record.get(key)}
    return json.dumps({"record": allowed, "outbound_action": "not_performed"})


def default_deepagents_tools() -> list[Any]:
    return [search_workspace_files, inspect_lead_record]
