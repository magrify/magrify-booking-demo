from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
import urllib.request
from datetime import date
from typing import Any


class BookingAdapter:
    """Small provider-neutral adapter for Magrify's Convex booking API.

    It is deliberately disabled until both the Convex HTTP URL and a scoped
    API key are configured. That keeps local agent runs dry-run safe.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("MAGRIFY_CONVEX_HTTP_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("MAGRIFY_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("MAGRIFY_CONVEX_HTTP_URL and MAGRIFY_API_KEY are required")

        def request() -> dict[str, Any]:
            body = None if payload is None else json.dumps(payload).encode("utf-8")
            request_obj = urllib.request.Request(
                f"{self.base_url}/api/v1/{path.lstrip('/')}",
                data=body,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request_obj, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))

        return await asyncio.to_thread(request)

    async def find_availability(
        self,
        *,
        property_slug: str,
        unit_type_slug: str,
        check_in: str,
        check_out: str,
    ) -> dict[str, Any]:
        query = urllib.parse.urlencode({
            "property": property_slug,
            "unitType": unit_type_slug,
            "from": check_in,
            "to": check_out,
        })
        result = await self._request("GET", f"availability?{query}")
        rows = result.get("units", []) if isinstance(result, dict) else []
        nights = (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days
        selected = next(
            (
                row for row in rows
                if not set(row.get("blockedDates", []))
                and nights > 0
            ),
            None,
        )
        rates = await self._request(
            "GET",
            f"rate-plans?{urllib.parse.urlencode({'property': property_slug, 'unitType': unit_type_slug})}",
        )
        rate_rows = rates.get("ratePlans", []) if isinstance(rates, dict) else []
        rate = rate_rows[0] if rate_rows else None
        return {
            "available": selected is not None and rate is not None,
            "unit_id": selected.get("unitId") if selected else None,
            "unit_name": selected.get("unitName") if selected else None,
            "rate_plan_id": rate.get("ratePlanId") if rate else None,
            "rate_plan_name": rate.get("name") if rate else None,
            "currency": rate.get("currency") if rate else None,
            "nightly_cents": rate.get("baseNightlyCents") if rate else None,
            "nights": nights,
        }

    async def create_hold(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "bookings/hold", payload)

