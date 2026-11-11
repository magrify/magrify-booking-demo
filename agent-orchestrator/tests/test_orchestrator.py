import asyncio
from pathlib import Path

from agent_orchestrator.agents import framework_status
from agent_orchestrator.data_controls import redact, validate_tenant_id
from agent_orchestrator.gateway import ModelGateway
from agent_orchestrator.store import Store
from agent_orchestrator.workflows import build_context_chain, build_workflow
from agent_orchestrator.evaluations import evaluate_workflow_state
from agent_orchestrator.prompt_eval import optimize_prompt_context, score_variant
from agent_orchestrator.banking_controls import review_lender_package
from agent_orchestrator.search_adapters import file_search, vector_search
from agent_orchestrator.load_test import run_validation_load
from agent_orchestrator.deepagents_tools import default_deepagents_tools


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


def test_prompt_context_optimization_measures_scoped_improvement():
    baseline = score_variant("baseline")
    optimized = score_variant("tenant_scoped_v2")
    result = optimize_prompt_context(iterations=2)
    assert optimized["mean_score"] > baseline["mean_score"]
    assert result["selected"]["variant"] == "tenant_scoped_v2"
    assert result["improvement"] > 0


def test_reliability_report_counts_observed_runs_and_events(tmp_path: Path):
    store = Store(str(tmp_path / "monitor.sqlite3"))
    run_id = store.create_run(
        product="magrify",
        workflow="phone_concierge",
        tenant_id="property:demo",
        payload={"property_slug": "demo"},
        approval_required=True,
    )
    store.event(run_id, "run_started", {"product": "magrify"})
    store.event(run_id, "approval_decision", {"approved": True})
    store.event(run_id, "approval_resumed", {"status": "confirmed"})
    store.finish_run(run_id, status="confirmed", output={"status": "confirmed"})
    report = store.reliability_report("property:demo")
    assert report["observed_runs"] == 1
    assert report["confirmed_runs"] == 1
    assert report["completion_rate"] == 1.0
    assert report["approval_resume_rate"] == 1.0


def test_banking_controls_route_without_making_credit_decisions():
    result = review_lender_package({
        "case_id": "case-1",
        "property_id": "property-1",
        "documents": ["rent_roll", "operating_statement", "inspection_report", "insurance"],
        "exceptions": ["insurance expires before requested close"],
    })
    assert result["status"] == "exception_review"
    assert result["next_step"] == "route_to_human_underwriter"
    assert result["credit_decision"] == "not_made_by_agent"


def test_vector_rag_and_file_search_are_tenant_scoped(tmp_path: Path):
    rows = [
        {"id": "doc-1", "title": "Cancellation", "content": "30 amp cancellation policy", "tags": ["policy"]},
        {"id": "doc-2", "title": "Amenities", "content": "Cabin linens included", "tags": ["amenity"]},
    ]
    vector_results = vector_search(rows, "30 amp cancellation")
    assert vector_results[0]["id"] == "doc-1"

    tenant_dir = tmp_path / "property_demo"
    tenant_dir.mkdir()
    (tenant_dir / "policies.md").write_text("Cancellation is free until seven days before arrival.", encoding="utf-8")
    assert file_search(tmp_path, "property:demo", "cancellation")
    assert file_search(tmp_path, "property:other", "cancellation") == []


def test_adoption_report_distinguishes_signoff_and_usage(tmp_path: Path):
    store = Store(str(tmp_path / "adoption.sqlite3"))
    store.tenant_event("property:demo", "demo_presented", {"actor_role": "operator"})
    store.tenant_event("property:demo", "deployment_configured", {"actor_role": "operator"})
    report = store.adoption_report("property:demo")
    assert report["observed_adoption_events"] == 2
    assert report["signoff_recorded"] is False
    assert report["staff_usage_recorded"] is False


def test_synthetic_load_harness_exercises_reliability_metrics(tmp_path: Path):
    result = run_validation_load(tmp_path / "load.sqlite3", runs=20)
    report = result["report"]
    assert result["mode"] == "synthetic_validation"
    assert report["observed_runs"] == 20
    assert report["confirmed_runs"] > 0
    assert report["failed_runs"] > 0
    assert report["awaiting_approval_runs"] > 0


def test_deepagents_research_tools_are_read_only_and_bounded():
    tools = default_deepagents_tools()
    assert {tool.name for tool in tools} == {"search_workspace_files", "inspect_lead_record"}
    result = tools[1].invoke('{"name":"A","company":"Example","email":"a@example.com","secret":"redact"}')
    assert "outbound_action" in result
    assert "secret" not in result


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

