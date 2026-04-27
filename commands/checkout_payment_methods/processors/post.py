"""Output shaping for checkout payment methods."""

from __future__ import annotations

import json


def _method_type(method: dict[str, object]) -> str:
    if method.get("isApplePay") is True:
        return "apple_pay"
    if method.get("isGooglePay") is True:
        return "google_pay"
    if method.get("isGiftCard") is True:
        return "gift_card"
    if method.get("isSocialCard") is True:
        return "social_card"
    if method.get("isAdvanceInvoice") is True:
        return "advance_invoice"
    if method.get("isCard") is True:
        return "card"
    return "bank_link"


def _shape_method(method: object) -> dict[str, object]:
    if not isinstance(method, dict):
        raise ValueError("Expected payment method object")
    return {
        "code": method.get("code"),
        "title": method.get("title"),
        "type": _method_type(method),
        "is_card": method.get("isCard") is True,
        "one_click_pay_supported": method.get("isOneClickPaySupported") is True,
        "is_recurring": method.get("isRecurring") is True,
        "is_gift_card": method.get("isGiftCard") is True,
        "reserved_amount": method.get("reservedAmount"),
        "max_amount": method.get("maxAmount"),
        "logo_url": method.get("logoUrl"),
    }


def _shape_saved_card(card: object) -> dict[str, object]:
    if not isinstance(card, dict):
        raise ValueError("Expected saved card object")
    return {
        "id": card.get("id"),
        "type": card.get("type"),
        "pan_number": card.get("panNumber"),
        "method_code": card.get("methodCode"),
        "default": card.get("isDefault") is True,
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
    if not isinstance(payload, dict):
        raise ValueError("Expected response JSON object")

    methods = payload.get("methods") or []
    cards = payload.get("cards") or []
    if not isinstance(methods, list) or not isinstance(cards, list):
        raise ValueError("Expected methods and cards arrays")

    shaped_methods = [_shape_method(method) for method in methods]
    shaped_cards = [_shape_saved_card(card) for card in cards]

    context["output"] = {
        "cart_id": args.get("cart_id"),
        "count": len(shaped_methods),
        "methods": shaped_methods,
        "saved_cards_count": len(shaped_cards),
        "saved_cards": shaped_cards,
    }
    return context
