"""Output shaping for checkout choose-time-slot."""

from __future__ import annotations

import json


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get("response")
    args = context.get("args")
    if not isinstance(response, dict) or not isinstance(args, dict):
        raise ValueError("Missing processor context")

    body = response.get("body")
    if not isinstance(body, str):
        raise ValueError("Expected JSON response body")

    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object response body")

    status = int(response.get("status", 0))
    next_url = payload.get("deliveryNextUrl")
    modal_required = payload.get("isModalRequired")

    context["output"] = {
        "selected": 200 <= status < 300,
        "time_id": str(args.get("time_id")),
        "next_url": next_url if isinstance(next_url, str) else None,
        "modal_required": modal_required if isinstance(modal_required, bool) else None,
    }
    return context
