"""Output shaping for checkout prices."""

from __future__ import annotations

import json
import re


_MONEY_RE = re.compile(r"(-?\d+(?:[,.]\d+)?)\s*€")
_NUMBER_RE = re.compile(r"(-?\d+(?:[,.]\d+)?)")


def _to_number(value: object) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value) if float(value).is_integer() else value
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace(",", ".")
    if not normalized:
        return None
    try:
        number = float(normalized)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _amount_from_formatted(formatted: object) -> int | float | None:
    if not isinstance(formatted, str):
        return None
    match = _MONEY_RE.search(formatted) or _NUMBER_RE.search(formatted)
    if not match:
        return None
    return _to_number(match.group(1))


def _shape_row(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise ValueError("Expected price row object")
    formatted = row.get("formatted")
    value = row.get("value")
    amount = _to_number(value) if value is not None else _amount_from_formatted(formatted)
    return {
        "type": row.get("type"),
        "amount": amount,
        "formatted": formatted,
        "currency": "EUR" if isinstance(formatted, str) and "€" in formatted else None,
    }


def _find(rows: list[dict[str, object]], row_type: str) -> dict[str, object] | None:
    row = next((row for row in rows if row.get("type") == row_type), None)
    if row is None or row.get("formatted") is None:
        return None
    return {
        "amount": row.get("amount"),
        "formatted": row.get("formatted"),
        "currency": row.get("currency"),
    }


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get("response")
    args = context.get("args")
    if not isinstance(response, dict) or not isinstance(args, dict):
        raise ValueError("Missing processor context")

    body = response.get("body")
    if not isinstance(body, str):
        raise ValueError("Expected JSON response body")

    payload = json.loads(body)
    if not isinstance(payload, list):
        raise ValueError("Expected response JSON array")

    breakdown = [_shape_row(row) for row in payload]
    context["output"] = {
        "cart_id": args.get("cart_id"),
        "currency": "EUR",
        "total_price": _find(breakdown, "totalPrice"),
        "left_to_pay": _find(breakdown, "leftToPay"),
        "vat": _find(breakdown, "vat"),
        "rimi_money_earned": _find(breakdown, "rimiMoneyEarned"),
        "rimi_money_spent": _find(breakdown, "rimiMoneySpent"),
        "social_card_balance_spent": _find(breakdown, "socialCardBalanceSpent"),
        "order_discounts": _find(breakdown, "orderDiscounts"),
    }
    return context
