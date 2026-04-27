"""Request preparation for cart update-item."""

from __future__ import annotations

from datetime import UTC, datetime


def _format_quantity(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Expected quantity to be a number")
    if isinstance(value, str):
        return value
    if isinstance(value, int) or value.is_integer():
        return str(int(value))
    return str(value)


def run(context: dict[str, object]) -> dict[str, object]:
    request = context.get("request")
    if not isinstance(request, dict):
        raise ValueError("Missing request context")

    body = request.get("body")
    if not isinstance(body, dict):
        raise ValueError("Expected request body to be an object")

    body["_method"] = "put"
    body["product"] = str(body.get("product"))
    body["amount"] = _format_quantity(body.get("amount"))

    headers = request.setdefault("headers", {})
    if not isinstance(headers, dict):
        raise ValueError("Expected request headers to be an object")
    headers["accept"] = "application/json"
    headers["content-type"] = "application/json"
    headers["origin"] = "https://www.rimi.ee"
    headers["referer"] = "https://www.rimi.ee/epood/en"
    headers["x-cart-update-timestamp"] = str(int(datetime.now(UTC).timestamp() * 1000))
    headers.pop("content-length", None)
    return context
