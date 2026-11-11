from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Product = Literal["magrify", "cartelbot"]
Workflow = Literal["booking_concierge", "prospector"]


class RunRequest(BaseModel):
    product: Product
    workflow: Workflow
    tenant_id: str = Field(min_length=1, max_length=160)
    input: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    provider: str | None = None
    require_approval: bool = True


class ApprovalRequest(BaseModel):
    approved: bool
    actor_id: str = Field(min_length=1, max_length=160)
    reason: str | None = None


class EvalRequest(BaseModel):
    run_id: str
    evaluator: str = "default"
    score: float = Field(ge=0, le=1)
    passed: bool
    notes: str | None = None

