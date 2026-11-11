from __future__ import annotations

import os
from typing import Any


class ModelGateway:
    """Provider-neutral model adapter. Secrets stay in the service environment."""

    async def complete(self, *, messages: list[dict[str, str]], provider: str | None = None, model: str | None = None, task: str | None = None) -> str:
        selected = provider or os.getenv("MODEL_PROVIDER", "openrouter")
        selected_model = model or self.route_model(task)
        if selected == "anthropic":
            return await self._anthropic(messages, selected_model)
        if selected == "openai":
            return await self._openai(messages, selected_model)
        return await self._openrouter(messages, selected_model)

    @staticmethod
    def route_model(task: str | None) -> str:
        if task in {"classify", "fit_score", "reply"}:
            return os.getenv("MODEL_CLASSIFIER", os.getenv("MODEL_NAME", "openai/gpt-4.1-mini"))
        if task in {"proposal", "research", "objection"}:
            return os.getenv("MODEL_PROPOSAL", os.getenv("MODEL_NAME", "openai/gpt-4.1-mini"))
        return os.getenv("MODEL_NAME", "openai/gpt-4.1-mini")

    async def _openai(self, messages: list[dict[str, str]], model: str) -> str:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return self._dry_run(messages, model)
        from openai import AsyncOpenAI

        response = await AsyncOpenAI(api_key=key).chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=self.max_output_tokens(),
        )
        return response.choices[0].message.content or ""

    async def _openrouter(self, messages: list[dict[str, str]], model: str) -> str:
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            return self._dry_run(messages, model)
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=key, base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=self.max_output_tokens(),
                extra_headers={"HTTP-Referer": "https://magrify.com", "X-Title": "Magrify CartelBot agent orchestrator"},
            )
            return response.choices[0].message.content or ""
        except Exception:
            if os.getenv("OPENAI_API_KEY"):
                return await self._openai(messages, os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4.1-mini"))
            return self._dry_run(messages, model)

    async def _anthropic(self, messages: list[dict[str, str]], model: str) -> str:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            return self._dry_run(messages, model)
        from anthropic import AsyncAnthropic

        system = "\n".join(message["content"] for message in messages if message["role"] == "system")
        user_messages = [{"role": message["role"], "content": message["content"]} for message in messages if message["role"] != "system"]
        response = await AsyncAnthropic(api_key=key).messages.create(
            model=model,
            max_tokens=self.max_output_tokens(),
            system=system or None,
            messages=user_messages,
        )
        return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")

    @staticmethod
    def max_output_tokens() -> int:
        """Bound generation cost unless an operator explicitly raises the cap."""
        try:
            return max(64, min(int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "400")), 2_000))
        except ValueError:
            return 400

    @staticmethod
    def _dry_run(messages: list[dict[str, str]], model: str) -> str:
        last = messages[-1]["content"] if messages else ""
        return f"DRY_RUN[{model}]: {last[:500]}"
