from __future__ import annotations

import re
from typing import Any


EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def validate_tenant_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        raise ValueError("Invalid tenant id")
    return value


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return PHONE.sub("[PHONE]", EMAIL.sub("[EMAIL]", value))
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact(item) for key, item in value.items()}
    return value
