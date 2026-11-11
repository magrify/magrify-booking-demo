from __future__ import annotations

from typing import Any


async def run_deep_research_agent(model: str, prompt: str, tools: list[Any] | None = None) -> str:
    """Run a read-only Deep Agents research pass when explicitly enabled.

    Deep Agents is intentionally kept behind this small adapter so the
    prospector graph can switch it off without changing its state machine.
    The agent receives no side-effecting tools and is instructed to return a
    bounded research memo rather than contacting a prospect.
    """
    agent = build_deep_research_agent(model, tools=tools)
    result = await agent.ainvoke({
        "messages": [
            {
                "role": "user",
                "content": (
                    "Research the following business and ICP using only the tools available to you. "
                    "Return a concise memo with assumptions, evidence gaps, and recommended next steps. "
                    "Do not send messages, publish content, or change external systems.\n\n"
                    f"{prompt}"
                ),
            }
        ]
    })
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if messages:
        content = getattr(messages[-1], "content", messages[-1])
    else:
        content = result
    if isinstance(content, list):
        content = " ".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
    return str(content)[:12000]


def _input_guardrail(_ctx: Any, _agent: Any, value: Any) -> Any:
    from agents import GuardrailFunctionOutput

    text = str(value).lower()
    blocked = any(marker in text for marker in ("ignore approval", "bypass approval", "reveal api key", "send without approval"))
    return GuardrailFunctionOutput(
        output_info={"blocked_instruction": blocked},
        tripwire_triggered=blocked,
    )


def _output_guardrail(_ctx: Any, _agent: Any, value: Any) -> Any:
    from agents import GuardrailFunctionOutput

    text = str(value).lower()
    unsafe_claim = any(marker in text for marker in ("payment succeeded", "refund completed", "message sent", "published successfully"))
    return GuardrailFunctionOutput(
        output_info={"unsafe_external_claim": unsafe_claim},
        tripwire_triggered=unsafe_claim,
    )


def framework_status() -> dict[str, bool]:
    status: dict[str, bool] = {}
    for module in ("langchain", "langgraph", "deepagents", "anthropic", "agents"):
        try:
            __import__(module)
            status[module] = True
        except ImportError:
            status[module] = False
    return status


def build_openai_agent(name: str, instructions: str, tools: list[Any] | None = None) -> Any:
    from agents import Agent, InputGuardrail, OutputGuardrail

    return Agent(
        name=name,
        instructions=instructions,
        tools=tools or [],
        input_guardrails=[InputGuardrail(guardrail_function=_input_guardrail, name="approval_and_secret_safety")],
        output_guardrails=[OutputGuardrail(guardrail_function=_output_guardrail, name="external_side_effect_claims")],
    )


def build_deep_research_agent(model: str, tools: list[Any] | None = None) -> Any:
    from deepagents import create_deep_agent
    from .deepagents_tools import default_deepagents_tools

    return create_deep_agent(model=model, tools=tools if tools is not None else default_deepagents_tools(), system_prompt="Research carefully, cite evidence in the run record, and stop before external side effects.")

