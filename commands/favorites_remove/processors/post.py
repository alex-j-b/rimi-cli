"""Output shaping for favorites remove."""

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
    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        context["output"] = {
            "favorited": True,
            "product_id": str(args.get("product_id")),
            "message": payload["message"],
        }
        return context

    context["output"] = {
        "favorited": not (200 <= int(response.get("status", 0)) < 300),
        "product_id": str(args.get("product_id")),
        "message": None,
    }
    return context
