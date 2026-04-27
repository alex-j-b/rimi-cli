"""Request preparation for favorites list."""

from __future__ import annotations


def run(context: dict[str, object]) -> dict[str, object]:
    request = context.get("request")
    if not isinstance(request, dict):
        raise ValueError("Missing request context")

    headers = request.setdefault("headers", {})
    if not isinstance(headers, dict):
        raise ValueError("Expected request headers to be an object")
    headers["accept"] = "application/json"
    headers["referer"] = "https://www.rimi.ee/epood/en/my-profile/favourites"
    return context
