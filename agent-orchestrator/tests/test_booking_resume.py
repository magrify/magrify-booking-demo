import asyncio

from langgraph.checkpoint.memory import MemorySaver

from agent_orchestrator.gateway import ModelGateway
from agent_orchestrator.store import Store
from agent_orchestrator import workflows


class FakeBookingAdapter:
    configured = True

    async def find_availability(self, *, property_slug, unit_type_slug, check_in, check_out):
        return {
            "available": True,
            "unit_id": "unit-evidence-1",
            "unit_name": "Site 1",
            "rate_plan_id": "rate-evidence-1",
            "rate_plan_name": "Standard",
            "currency": "USD",
            "nightly_cents": 10000,
            "nights": 2,
        }

    async def create_hold(self, payload):
        return {
            "bookingId": "booking-evidence-1",
            "confirmationCode": "CONF-EVIDENCE-1",
            "unitId": payload["unitId"],
        }


class FakeGateway(ModelGateway):
    async def complete(self, *, messages, provider=None, model=None, task=None):
        return "Use only the approved booking context and hand off safely."


def test_booking_approval_resumes_saved_thread_and_persists_confirmation(monkeypatch, tmp_path):
    monkeypatch.setattr(workflows, "BookingAdapter", FakeBookingAdapter)
    graph = workflows.build_workflow(
        Store(str(tmp_path / "booking-evidence.sqlite3")),
        FakeGateway(),
        checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": "booking-evidence-thread"}}
    initial = asyncio.run(
        graph.ainvoke(
            {
                "product": "magrify",
                "workflow": "phone_concierge",
                "tenant_id": "property:evidence",
                "approval_required": True,
                "input": {
                    "property_slug": "evidence-property",
                    "unit_type_slug": "rv-site",
                    "check_in": "2030-07-10",
                    "check_out": "2030-07-12",
                    "adults": 2,
                    "children": 0,
                    "message": "Need a two-night site",
                    "hold_requested": True,
                    "payment_status": "paid",
                },
            },
            config=config,
        )
    )
    resumed = asyncio.run(
        graph.ainvoke(
            {
                **initial,
                "approval_required": False,
            },
            config=config,
        )
    )
    snapshot = asyncio.run(graph.aget_state(config))

    assert initial["status"] == "awaiting_approval"
    assert resumed["status"] == "confirmed"
    assert resumed["hold"]["bookingId"] == "booking-evidence-1"
    assert resumed["payment"]["status"] == "paid"
    assert snapshot.values["status"] == "confirmed"
    assert snapshot.config["configurable"]["thread_id"] == "booking-evidence-thread"
