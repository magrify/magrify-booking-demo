"""Provider-neutral vector RAG and tenant-scoped file-search adapters."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}", re.IGNORECASE)
ALLOWED_FILE_TYPES = {".md", ".txt", ".json", ".csv"}


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _vector(text: str, dimensions: int = 96) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def vector_search(rows: list[dict[str, Any]], query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Run a small deterministic vector-RAG search over already tenant-scoped rows."""
    query_vector = _vector(query)
    scored: list[dict[str, Any]] = []
    for row in rows:
        content = f"{row.get('title', '')} {row.get('content', '')} {' '.join(row.get('tags', []))}"
        score = _cosine(query_vector, _vector(content))
        if score > 0:
            scored.append({**row, "vector_score": round(score, 4)})
    scored.sort(key=lambda item: item["vector_score"], reverse=True)
    return scored[: max(1, limit)]


def tenant_file_key(tenant_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", tenant_id).strip("_") or "tenant"


def file_search(root: str | Path, tenant_id: str, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search bounded tenant files without allowing path traversal."""
    base = Path(root).expanduser().resolve()
    tenant_root = (base / tenant_file_key(tenant_id)).resolve()
    if base not in tenant_root.parents and tenant_root != base:
        raise ValueError("tenant file root escaped configured search root")
    if not tenant_root.exists():
        return []
    terms = set(_tokens(query))
    results: list[dict[str, Any]] = []
    for path in tenant_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_FILE_TYPES:
            continue
        try:
            text = path.read_text(encoding="utf-8")[:250_000]
        except (OSError, UnicodeDecodeError):
            continue
        haystack = f"{path.name} {text}".lower()
        hits = sum(term in haystack for term in terms)
        if hits:
            results.append({"path": str(path.relative_to(base)), "content": text[:4000], "score": hits})
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[: max(1, limit)]
