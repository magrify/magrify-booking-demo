from __future__ import annotations

import os
from typing import Any, TypedDict

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from .agents import build_openai_agent, run_deep_research_agent
from .booking import BookingAdapter
from .enrichment_worker import score_lead
from .gateway import ModelGateway
from .store import Store

try:
    from agents import trace
except ImportError:  # optional during minimal local installs
    trace = None


class WorkflowState(TypedDict, total=False):
    product: str
    workflow: str
    tenant_id: str
    input: dict[str, Any]
    context: list[dict[str, Any]]
    qualification: dict[str, Any]
    draft: str
    approval_required: bool
    status: str
    runtime: str
    action: str
    error: str
    availability: dict[str, Any]
    hold: dict[str, Any]
    payment: dict[str, Any]
    discovery: dict[str, Any]
    enrichment: dict[str, Any]
    fit_score: dict[str, Any]
    approval: dict[str, Any]
    reply_classification: dict[str, Any]
    meeting: dict[str, Any]
    revenue: dict[str, Any]
    research_output: str


def build_workflow(store: Store, gateway: ModelGateway, *, checkpointer: Any | None = None):
    context_chain = build_context_chain()
    booking_adapter = BookingAdapter()

    async def retrieve(state: WorkflowState) -> WorkflowState:
        namespace = "property" if state["product"] == "magrify" else "campaign"
        query = str(state["input"].get("message") or state["input"].get("business_description") or state["input"].get("query") or "")
        chain_result = context_chain.invoke(query)
        return {**state, "context": store.search_knowledge(state["tenant_id"], namespace, chain_result["context_query"]), "runtime": chain_result["retrieval_mode"]}

    async def qualify(state: WorkflowState) -> WorkflowState:
        payload = state["input"]
        if state["product"] == "magrify":
            # Phone callers can qualify before they disclose email; the agent
            # only needs a request plus dates to check inventory. Email is
            # collected before a hold/payment handoff.
            required = ["message", "check_in", "check_out"]
            score = sum(bool(payload.get(key)) for key in required) / len(required)
            result = {"qualified": score >= 1, "score": score, "reason": "guest request and stay dates present" if score >= 1 else "missing request or stay dates"}
        else:
            score = 1.0 if payload.get("business_description") and payload.get("icp") else 0.0
            result = {"qualified": score == 1, "score": score, "reason": "business description and ICP supplied" if score else "missing business description or ICP"}
        return {**state, "qualification": result}

    async def discover(state: WorkflowState) -> WorkflowState:
        if state["product"] != "cartelbot":
            return state
        payload = state["input"]
        return {
            **state,
            "discovery": {
                "business": str(payload.get("business_description", "")).strip(),
                "icp": str(payload.get("icp", "")).strip(),
                "offer": str(payload.get("offer", "")).strip(),
                "channels": payload.get("channels") or ["email", "linkedin", "x"],
            },
        }

    async def enrich(state: WorkflowState) -> WorkflowState:
        if state["product"] != "cartelbot":
            return state
        leads = state["input"].get("leads") or []
        if not isinstance(leads, list):
            leads = []
        icp = str(state["input"].get("icp", ""))
        enriched = []
        for lead in leads[:500]:
            if isinstance(lead, dict):
                item = dict(lead)
                item.update(score_lead(item, icp))
                enriched.append(item)
        completeness = sum(item.get("completeness", 0) for item in enriched) / max(len(enriched), 1)
        result: WorkflowState = {**state, "enrichment": {"leads": enriched, "lead_count": len(enriched), "completeness": round(completeness, 4)}}
        # Deep Agents is an opt-in research pass. It is read-only and its
        # output is stored in the run for review; no outbound action is wired
        # into the Deep Agents tool list.
        if os.getenv("ENABLE_DEEPAGENTS", "false").lower() == "true":
            provider_ready = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
            if provider_ready:
                try:
                    model = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-4.1-mini")
                    memo = await run_deep_research_agent(
                        model,
                        f"Business: {state['input'].get('business_description', '')}\n"
                        f"ICP: {state['input'].get('icp', '')}\n"
                        f"Offer: {state['input'].get('offer', '')}\n"
                        f"Lead sample: {enriched[:20]}",
                    )
                    result["research_output"] = memo
                except Exception as error:
                    result["research_output"] = f"Deep Agents unavailable: {type(error).__name__}"
        return result

    async def fit_score(state: WorkflowState) -> WorkflowState:
        if state["product"] != "cartelbot":
            return state
        leads = state.get("enrichment", {}).get("leads", [])
        scores = [float(item.get("fit_score", 0)) for item in leads if isinstance(item, dict)]
        average = sum(scores) / max(len(scores), 1)
        qualified = [item for item in leads if isinstance(item, dict) and item.get("fit_label") == "high"]
        return {**state, "fit_score": {"average": round(average, 4), "qualified_count": len(qualified), "qualified_leads": qualified}}

    async def approval(state: WorkflowState) -> WorkflowState:
        if state["product"] != "cartelbot":
            return state
        if state.get("approval_required", True):
            return {**state, "approval": {"required": True}, "status": "awaiting_approval", "action": "approve_outreach"}
        return {**state, "approval": {"required": False, "approved": True}, "status": "approved", "action": "prepare_outreach"}

    async def outreach(state: WorkflowState) -> WorkflowState:
        if state["product"] != "cartelbot":
            return state
        if state.get("approval_required", True):
            return state
        # This creates a draft only. The Cloudflare Worker/CRM must still
        # perform an explicit human approval before any external send.
        return {**state, "action": "outreach_ready", "status": "outreach_ready"}

    async def classify_reply(state: WorkflowState) -> WorkflowState:
        if state["product"] != "cartelbot":
            return state
        text = str(state["input"].get("reply", "")).lower().strip()
        if not text:
            return state
        if any(term in text for term in ("unsubscribe", "remove me", "do not contact")):
            label = "opt_out"
        elif any(term in text for term in ("book", "schedule", "calendar", "call")):
            label = "meeting_intent"
        elif any(term in text for term in ("not interested", "no thanks", "pass")):
            label = "negative"
        else:
            label = "needs_human_review"
        return {**state, "reply_classification": {"label": label, "confidence": 0.9 if label != "needs_human_review" else 0.5}, "action": "suppress_contact" if label == "opt_out" else "handoff_to_human" if label == "needs_human_review" else state.get("action")}

    async def meeting(state: WorkflowState) -> WorkflowState:
        if state["product"] != "cartelbot" or not state["input"].get("meeting_booked"):
            return state
        return {**state, "meeting": {"booked": True, "calendar_event_id": state["input"].get("calendar_event_id")}, "status": "meeting_booked", "action": "track_meeting"}

    async def revenue(state: WorkflowState) -> WorkflowState:
        if state["product"] != "cartelbot":
            return state
        amount = state["input"].get("revenue_cents")
        if not isinstance(amount, (int, float)) or amount <= 0:
            return state
        return {**state, "revenue": {"amount_cents": int(amount), "currency": state["input"].get("currency", "USD")}, "status": "revenue_attributed", "action": "record_revenue"}

    async def availability(state: WorkflowState) -> WorkflowState:
        if state["product"] != "magrify":
            return state
        payload = state["input"]
        required = (payload.get("property_slug"), payload.get("unit_type_slug"), payload.get("check_in"), payload.get("check_out"))
        if not all(required):
            return {**state, "status": "needs_information", "action": "collect_property_and_stay_details"}
        if not booking_adapter.configured:
            return {**state, "status": "awaiting_configuration", "action": "connect_magrify_booking_api"}
        try:
            result = await booking_adapter.find_availability(
                property_slug=str(payload["property_slug"]),
                unit_type_slug=str(payload["unit_type_slug"]),
                check_in=str(payload["check_in"]),
                check_out=str(payload["check_out"]),
            )
        except Exception as error:
            return {**state, "status": "availability_failed", "action": "handoff_to_staff", "error": type(error).__name__}
        return {**state, "availability": result, "status": "available" if result.get("available") else "unavailable", "action": "offer_available_options" if result.get("available") else "handoff_to_staff"}

    async def hold(state: WorkflowState) -> WorkflowState:
        if state["product"] != "magrify" or state.get("status") != "available":
            return state
        payload = state["input"]
        if not payload.get("hold_requested"):
            return {**state, "action": "ask_guest_to_confirm_hold"}
        if state.get("approval_required", True):
            return {**state, "status": "awaiting_approval", "action": "approve_temporary_hold"}
        if not booking_adapter.configured:
            return {**state, "status": "awaiting_configuration", "action": "connect_magrify_booking_api"}
        availability = state.get("availability", {})
        try:
            result = await booking_adapter.create_hold({
                "unitId": availability.get("unit_id"),
                "ratePlanId": availability.get("rate_plan_id"),
                "checkIn": payload["check_in"],
                "checkOut": payload["check_out"],
                "adults": int(payload.get("adults", 1)),
                "children": int(payload.get("children", 0)),
                "guest": payload.get("guest", {}),
                "addOns": payload.get("add_ons", []),
                **({"promoCode": payload["promo_code"]} if payload.get("promo_code") else {}),
            })
        except Exception as error:
            return {**state, "status": "hold_failed", "action": "handoff_to_staff", "error": type(error).__name__}
        return {**state, "hold": result, "status": "payment_ready", "action": "send_payment_link"}

    async def payment(state: WorkflowState) -> WorkflowState:
        if state["product"] != "magrify" or state.get("status") not in {"payment_ready", "awaiting_payment"}:
            return state
        hold_result = state.get("hold", {})
        booking_id = hold_result.get("bookingId") or hold_result.get("booking_id")
        confirmation = hold_result.get("confirmationCode") or hold_result.get("confirmation_code")
        if not booking_id or not confirmation:
            return {**state, "status": "payment_ready", "action": "send_payment_link"}
        payment_status = state["input"].get("payment_status")
        payment_url = f"{os.getenv('MAGRIFY_SITE_URL', 'https://booking.magrify.com').rstrip('/')}/checkout/{booking_id}?confirmation={confirmation}"
        if payment_status == "paid":
            return {**state, "payment": {"status": "paid", "url": payment_url}, "status": "confirmed", "action": "send_confirmation"}
        if payment_status == "abandoned":
            return {**state, "payment": {"status": "abandoned", "url": payment_url}, "status": "recovery_due", "action": "schedule_recovery"}
        return {**state, "payment": {"status": "pending", "url": payment_url}, "status": "awaiting_payment", "action": "send_payment_link"}

    async def draft(state: WorkflowState) -> WorkflowState:
        runtime_agent = build_openai_agent(
            'Magrify booking concierge' if state['product'] == 'magrify' else 'CartelBot prospector',
            'Use only approved tools and never claim external side effects completed.',
        )
        prompt = f"Product={state['product']} workflow={state['workflow']} input={state['input']} context={state.get('context', [])} qualification={state.get('qualification', {})}"
        tracing_enabled = os.getenv("OPENAI_AGENTS_TRACING", "false").lower() == "true"
        if trace is not None:
            with trace(
                "magrify-booking" if state["product"] == "magrify" else "cartelbot-prospector",
                group_id=state.get("tenant_id"),
                metadata={"workflow": state.get("workflow", ""), "runtime": "langgraph"},
                disabled=not tracing_enabled,
            ):
                draft_text = await gateway.complete(messages=[{"role": "system", "content": "You are a constrained product agent. Never claim an external action was completed."}, {"role": "user", "content": prompt}], task="proposal" if state["product"] == "cartelbot" else "booking")
        else:
            draft_text = await gateway.complete(messages=[{"role": "system", "content": "You are a constrained product agent. Never claim an external action was completed."}, {"role": "user", "content": prompt}], task="proposal" if state["product"] == "cartelbot" else "booking")
        framework_runtime = f"openai-agents-sdk:{runtime_agent.name}"
        if state["product"] == "cartelbot":
            framework_runtime += "+deepagents-ready"
            if state.get("research_output"):
                framework_runtime += "+deepagents-active"
            elif os.getenv("ENABLE_DEEPAGENTS", "false").lower() == "true":
                framework_runtime += "+deepagents-config-required"
        current_status = state.get("status")
        if not current_status:
            current_status = "awaiting_approval" if state.get("approval_required", True) else "ready"
        return {**state, "draft": draft_text, "runtime": framework_runtime, "status": current_status}

    graph = StateGraph(WorkflowState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("qualify", qualify)
    graph.add_node("discover", discover)
    graph.add_node("enrich", enrich)
    graph.add_node("fit_score", fit_score)
    graph.add_node("approval", approval)
    graph.add_node("outreach", outreach)
    graph.add_node("availability", availability)
    graph.add_node("hold", hold)
    graph.add_node("payment", payment)
    graph.add_node("draft", draft)
    graph.add_node("classify_reply", classify_reply)
    graph.add_node("meeting", meeting)
    graph.add_node("revenue", revenue)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "qualify")
    graph.add_edge("qualify", "discover")
    graph.add_edge("discover", "enrich")
    graph.add_edge("enrich", "fit_score")
    graph.add_edge("fit_score", "approval")
    graph.add_edge("approval", "availability")
    graph.add_edge("availability", "hold")
    graph.add_edge("hold", "payment")
    graph.add_edge("payment", "outreach")
    graph.add_edge("outreach", "classify_reply")
    graph.add_edge("classify_reply", "meeting")
    graph.add_edge("meeting", "revenue")
    graph.add_edge("revenue", "draft")
    graph.add_edge("draft", END)
    return graph.compile(checkpointer=checkpointer)


def build_context_chain() -> RunnableLambda:
    return RunnableLambda(lambda value: {"context_query": str(value).strip(), "retrieval_mode": "vectorless"})

