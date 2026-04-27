"""Output shaping for wallet apply."""

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

    status = int(response.get("status", 0))
    context["output"] = {
        "applied": 200 <= status < 300,
        "amount": args.get("amount"),
        "currency": "EUR",
        "message": payload.get("message") if isinstance(payload, dict) else None,
    }
    return context
