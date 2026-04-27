"""Output shaping for current order state."""

from __future__ import annotations

import json
import re


_MONEY_RE = re.compile(r"(-?\d+(?:[,.]\d+)?)")
_RIMI_BASE_URL = "https://www.rimi.ee"


def _to_number(value: object) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value) if float(value).is_integer() else value
    if not isinstance(value, str):
        return None
    match = _MONEY_RE.search(value.strip())
    if not match:
        return None
    try:
        number = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _money(value: object, currency_symbol: object = "€") -> dict[str, object] | None:
    if value in (None, ""):
        return None
    amount = _to_number(value)
    formatted = str(value)
    return {
        "amount": amount,
        "formatted": formatted,
        "currency": "EUR" if currency_symbol in {"€", "EUR"} or "€" in formatted else None,
    }


def _absolute_url(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/"):
        return f"{_RIMI_BASE_URL}{value}"
    return value


def _analytics_products(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = payload.get("gaDataLayerRows")
    if not isinstance(rows, list):
        return {}

    products_by_id: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ecommerce = row.get("ecommerce")
        if not isinstance(ecommerce, dict):
            continue
        purchase = ecommerce.get("purchase")
        if not isinstance(purchase, dict):
            continue
        products = purchase.get("products")
        if not isinstance(products, list):
            continue
        for product in products:
            if not isinstance(product, dict):
                continue
            product_id = product.get("id")
            if isinstance(product_id, str) and product_id != "SHP_BAG":
                products_by_id[product_id] = product
    return products_by_id


def _sorted_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return []

    def sort_key(item: tuple[object, object]) -> tuple[int, str]:
        key = str(item[0])
        return (int(key), key) if key.isdigit() else (10**9, key)

    ordered: list[dict[str, object]] = []
    for _, entry in sorted(entries.items(), key=sort_key):
        if isinstance(entry, dict):
            ordered.append(entry)
    return ordered


def _shape_item(entry: dict[str, object], analytics: dict[str, dict[str, object]]) -> dict[str, object]:
    product_id = entry.get("productCode")
    analytics_item = analytics.get(product_id) if isinstance(product_id, str) else None
    if analytics_item is None:
        analytics_item = {}

    return {
        "product_id": product_id,
        "name": entry.get("productName") or analytics_item.get("name"),
        "quantity": analytics_item.get("quantity"),
        "unit_price": _money(analytics_item.get("price"), analytics_item.get("currency")),
        "total_discount": _money(entry.get("totalDiscount"), entry.get("currencySymbol")),
        "in_stock": entry.get("isNotInStock") is not True,
        "purchasable": entry.get("isNotPurchasable") is not True,
        "url": _absolute_url(entry.get("productUrl")),
    }


def _empty_output(payload: object) -> dict[str, object]:
    signed_in = payload.get("isLoggedIn") if isinstance(payload, dict) else None
    signed_in_output = signed_in is True if signed_in is not None else None
    return {
        "active": False,
        "signed_in": signed_in_output,
        "message": "No current active order was returned.",
        "order_id": None,
    }


def _shape_order(payload: dict[str, object]) -> dict[str, object]:
    currency_symbol = payload.get("currencySymbol") or "€"
    entries = _sorted_entries(payload)
    analytics = _analytics_products(payload)
    items = [_shape_item(entry, analytics) for entry in entries]
    categories = payload.get("groupedProductCategories")
    category_names = list(categories.keys()) if isinstance(categories, dict) else []

    return {
        "active": True,
        "signed_in": payload.get("isLoggedIn") is True,
        "order_id": payload.get("orderNumber"),
        "status": payload.get("readableStatus"),
        "placed_at": payload.get("placedAt"),
        "customer_name": payload.get("getUsername"),
        "fulfillment": {
            "mode": "pickup" if payload.get("getDeliveryModeShortCode") == "cc" else "delivery",
            "mode_code": payload.get("getDeliveryModeShortCode"),
            "date": payload.get("getDeliveryDate"),
            "start_time": payload.get("deliveryStartTime"),
            "end_time": payload.get("deliveryEndTime"),
            "address": payload.get("deliveryAddressSuppressed"),
            "store": payload.get("storeDisplayName"),
            "express": payload.get("isExpressDelivery") is True,
            "can_change": payload.get("canChangeDelivery") is True,
        },
        "totals": {
            "currency": "EUR" if currency_symbol in {"€", "EUR"} else None,
            "total": _money(payload.get("totalPriceWithTax") or payload.get("totalPrice"), currency_symbol),
            "tax": _money(payload.get("totalTax"), currency_symbol),
            "delivery": _money(payload.get("deliveryCost"), currency_symbol),
            "packaging": _money(payload.get("packagingCost"), currency_symbol),
            "loyalty_points": _to_number(payload.get("loyaltyPointsTotal")),
            "rimi_money_earned": _to_number(payload.get("rimiMoneyEarned")),
            "stickers_earned": payload.get("stickersEarned"),
            "savings": _money(payload.get("totalCartSavings"), currency_symbol),
        },
        "item_count": len(items),
        "out_of_stock_count": sum(1 for item in items if item["in_stock"] is False),
        "not_purchasable_count": sum(1 for item in items if item["purchasable"] is False),
        "categories": category_names,
        "items": items,
    }


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get("response")
    if not isinstance(response, dict):
        raise ValueError("Missing response context")

    body = response.get("body")
    if body in (None, ""):
        context["output"] = _empty_output(None)
        return context
    if not isinstance(body, str):
        raise ValueError("Expected JSON response body")

    payload = json.loads(body)
    if not isinstance(payload, dict) or not payload.get("orderNumber"):
        context["output"] = _empty_output(payload)
        return context

    context["output"] = _shape_order(payload)
    return context
