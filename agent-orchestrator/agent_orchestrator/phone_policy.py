from __future__ import annotations

from typing import Any


BLOCKED_INPUT_MARKERS = ("ignore approval", "bypass approval", "reveal api key", "send without approval")
BLOCKED_OUTPUT_MARKERS = ("payment succeeded", "refund completed", "message sent", "published successfully")


def validate_phone_request(values: dict[str, Any]) -> None:
    text = " ".join(str(value) for value in values.values()).lower()
    if any(marker in text for marker in BLOCKED_INPUT_MARKERS):
        raise ValueError("approval and secret-safety policy blocked this request")
    email = str(values.get("email", ""))
    if len(email) > 254 or "\n" in email or "\r" in email:
        raise ValueError("invalid callback email")


def sanitize_phone_result(result: dict[str, Any]) -> dict[str, Any]:
    """Make the tool response explicit about what happened externally."""
    output = dict(result)
    status = str(output.get("status", ""))
    if status in {"payment_ready", "awaiting_payment", "available"}:
        output["payment_disclaimer"] = "No payment was collected on this call. Use the secure link to complete payment."
    if status == "confirmed":
        output["payment_disclaimer"] = "Confirmation was returned by the booking backend. Do not collect card details by phone."
    return output
