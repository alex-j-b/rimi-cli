"""Request preparation for product details."""

from __future__ import annotations


def run(context: dict[str, object]) -> dict[str, object]:
    request = context.get("request")
    if not isinstance(request, dict):
        raise ValueError("Missing request context")

    headers = request.setdefault("headers", {})
    if not isinstance(headers, dict):
        raise ValueError("Expected request headers to be an object")
    headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    return context
