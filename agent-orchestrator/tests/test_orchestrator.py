import asyncio
from pathlib import Path

from agent_orchestrator.agents import framework_status
from agent_orchestrator.data_controls import redact, validate_tenant_id
from agent_orchestrator.gateway import ModelGateway
from agent_orchestrator.store import Store
from agent_orchestrator.workflows import build_context_chain, build_workflow
from agent_orchestrator.evaluations import evaluate_workflow_state


def test_framework_status_is_safe():
    status = framework_status()
    assert set(status) == {"langchain", "langgraph", "deepagents", "anthropic", "agents"}


def test_openai_agent_has_safety_guardrails():
    from agent_orchestrator.agents import build_openai_agent

    agent = build_openai_agent("test", "safe")
    assert len(agent.input_guardrails) == 1
    assert len(agent.output_guardrails) == 1


def test_vectorless_context_chain():
    result = build_context_chain().invoke("30 amp campground cancellation")
    assert result == {"context_query": "30 amp campground cancellation", "retrieval_mode": "vectorless"}


def test_data_controls_redact_and_validate():
    assert redact({"email": "guest@example.com", "phone": "+1 555 555 1212"}) == {"email": "[EMAIL]", "phone": "[PHONE]"}
    assert validate_tenant_id("property:demo") == "property:demo"


def test_booking_graph_requires_configuration_before_side_effects(tmp_path: Path):
    graph = build_workflow(Store(str(tmp_path / "runs.sqlite3")), ModelGateway())
    state = asyncio.run(graph.ainvoke({
        "product": "magrify",
        "workflow": "phone_concierge",
        "tenant_id": "property:demo",
        "approval_required": True,
        "input": {
            "property_slug": "property-demo",
            "unit_type_slug": "rv-site",
            "check_in": "2030-07-10",
            "check_out": "2030-07-13",
            "adults": 2,
            "children": 0,
            "email": "guest@example.com",
            "message": "Need a site",
        },
    }))
    assert state["status"] == "awaiting_configuration"
    assert state["action"] == "connect_magrify_booking_api"


def test_deterministic_evaluation_checks_safety():
    result = evaluate_workflow_state({
        "product": "magrify",
        "tenant_id": "property:demo",
        "input": {"property_slug": "demo", "adults": 2, "children": 0},
        "status": "awaiting_configuration",
        "action": "connect_magrify_booking_api",
        "approval_required": True,
    })
    assert result["passed"] is True
    assert result["checks"]["no_unauthorized_refund"] is True


def test_cartelbot_pipeline_reaches_approval_and_scores_leads(tmp_path: Path):
    graph = build_workflow(Store(str(tmp_path / "runs.sqlite3")), ModelGateway())
    state = asyncio.run(graph.ainvoke({
        "product": "cartelbot",
        "workflow": "prospector",
        "tenant_id": "cartelbot:demo",
        "approval_required": True,
        "input": {
            "business_description": "campground booking software",
            "icp": "campground operators",
            "leads": [{"name": "A", "company": "Campground Co", "email": "a@example.com"}],
            "message": "Find qualified buyers",
        },
    }))
    assert state["status"] == "awaiting_approval"
    assert "fit_score" in state
    assert state["action"] == "approve_outreach"

