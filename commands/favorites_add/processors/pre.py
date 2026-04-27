"""Request preparation for favorites add."""

from __future__ import annotations


def run(context: dict[str, object]) -> dict[str, object]:
    request = context.get("request")
    if not isinstance(request, dict):
        raise ValueError("Missing request context")

    request["body"] = [{"name": "favorite", "value": ""}]

    headers = request.setdefault("headers", {})
    if not isinstance(headers, dict):
        raise ValueError("Expected request headers to be an object")
    headers["accept"] = "application/json, text/plain, */*"
    headers["content-type"] = "application/json"
    headers["origin"] = "https://www.rimi.ee"
    headers["referer"] = "https://www.rimi.ee/epood/en/my-profile/favourites"
    headers.pop("content-length", None)
    return context
