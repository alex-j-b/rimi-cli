"""Request preparation for wallet apply."""

from __future__ import annotations


def _format_amount(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Expected amount to be a number")
    if isinstance(value, str):
        amount = float(value)
    else:
        amount = float(value)
    if amount < 0:
        raise ValueError("Expected amount to be non-negative")
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def run(context: dict[str, object]) -> dict[str, object]:
    request = context.get("request")
    if not isinstance(request, dict):
        raise ValueError("Missing request context")

    body = request.get("body")
    if not isinstance(body, dict):
        raise ValueError("Expected request body to be an object")
    body["amount"] = _format_amount(body.get("amount"))

    headers = request.setdefault("headers", {})
    if not isinstance(headers, dict):
        raise ValueError("Expected request headers to be an object")
    headers["accept"] = "application/json"
    headers["content-type"] = "application/json"
    headers["origin"] = "https://www.rimi.ee"
    headers["referer"] = "https://www.rimi.ee/epood/en/checkout/summary/user"
    headers.pop("content-length", None)
    return context
