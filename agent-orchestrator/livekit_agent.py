"""LiveKit Agents worker for Magrify's phone booking concierge.

Install the optional `requirements-livekit.txt` before running this module.
The worker collects dates and party size, then delegates booking state and
approval to the shared orchestrator. It never talks to payment providers.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from typing import Any

from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, cli, function_tool, inference

from agent_orchestrator.phone_policy import sanitize_phone_result, validate_phone_request

load_dotenv()


async def create_booking_run(input_data: dict[str, Any]) -> dict[str, Any]:
    orchestrator = os.getenv("AGENT_ORCHESTRATOR_URL", "").rstrip("/")
    convex = os.getenv("MAGRIFY_CONVEX_HTTP_URL", "").rstrip("/")
    if not orchestrator and not convex:
        return {"status": "awaiting_configuration", "action": "connect_booking_backend"}

    def request() -> dict[str, Any]:
        if orchestrator:
            target = f"{orchestrator}/v1/livekit/booking"
            payload: dict[str, Any] = {
                "tenant_id": input_data.get("tenant_id") or os.getenv("MAGRIFY_TENANT_ID", "magrify-default"),
                "input": {**input_data, "channel": "phone"},
                "require_approval": True,
            }
            token = os.getenv("AGENT_ORCHESTRATOR_TOKEN", "").strip()
        else:
            target = f"{convex}/agent/booking"
            payload = {**input_data, "channel": "phone"}
            token = os.getenv("MAGRIFY_LIVEKIT_TOKEN", "").strip()
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(target, data=body, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    return await asyncio.to_thread(request)


async def create_knowledge_run(property_slug: str, question: str) -> dict[str, Any]:
    """Retrieve tenant-scoped property knowledge without exposing a database."""
    orchestrator = os.getenv("AGENT_ORCHESTRATOR_URL", "").rstrip("/")
    convex = os.getenv("MAGRIFY_CONVEX_HTTP_URL", "").rstrip("/")
    if not orchestrator and not convex:
        return {"status": "awaiting_configuration", "action": "connect_booking_backend"}

    def request() -> dict[str, Any]:
        if orchestrator:
            target = f"{orchestrator}/v1/livekit/knowledge"
            payload = {
                "tenant_id": os.getenv("MAGRIFY_TENANT_ID", "magrify-default"),
                "property_slug": property_slug,
                "question": question,
            }
            token = os.getenv("AGENT_ORCHESTRATOR_TOKEN", "").strip()
        else:
            target = f"{convex}/agent/knowledge"
            payload = {"property_slug": property_slug, "question": question}
            token = os.getenv("MAGRIFY_LIVEKIT_TOKEN", "").strip()
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(target, data=body, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        return await asyncio.to_thread(request)
    except Exception as error:
        return {"status": "knowledge_unavailable", "message": str(error)}


class MagrifyConcierge(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=(
            "You are Magrify's phone booking concierge. Collect the property, "
            "unit type, check-in date, check-out date, adults, children, and "
            "a callback email. Never claim availability until the booking tool "
            "returns it. Never collect card details or claim payment succeeded. "
            "Before creating a temporary hold, repeat the dates and ask the "
            "caller to confirm. Explain that payment continues in a secure link. "
            "For property policy or amenity questions, use the knowledge tool and "
            "only state facts returned by that tool."
        ))

    @function_tool()
    async def check_booking_options(
        self,
        context: RunContext,
        property_slug: str,
        unit_type_slug: str,
        check_in: str,
        check_out: str,
        adults: int,
        children: int = 0,
        email: str = "",
        hold_requested: bool = False,
    ) -> dict[str, Any]:
        """Check dates and optionally request an approval-gated temporary hold."""
        values = {
            "property_slug": property_slug,
            "unit_type_slug": unit_type_slug,
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "children": children,
            "email": email,
            "hold_requested": hold_requested,
            "message": "Phone booking request",
        }
        validate_phone_request(values)
        return sanitize_phone_result(await create_booking_run(values))

    @function_tool()
    async def answer_property_question(
        self,
        context: RunContext,
        property_slug: str,
        question: str,
    ) -> dict[str, Any]:
        """Answer a property question from the tenant's structured knowledge."""
        return await create_knowledge_run(property_slug.strip(), question.strip())


server = AgentServer()


@server.rtc_session(agent_name="magrify-booking-concierge")
async def entrypoint(ctx: JobContext) -> None:
    session = AgentSession(
        stt=inference.STT(model=os.getenv("LIVEKIT_STT_MODEL", "deepgram/nova-3")),
        llm=inference.LLM(model=os.getenv("LIVEKIT_LLM_MODEL", "openai/gpt-4.1-mini")),
        tts=inference.TTS(model=os.getenv("LIVEKIT_TTS_MODEL", "cartesia/sonic-3")),
        transcription_timeout=5.0,
    )
    await session.start(agent=MagrifyConcierge(), room=ctx.room)
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)

