"""Output shaping for products categories."""

from __future__ import annotations

import json
import re


_CATEGORY_ID_RE = re.compile(r"/c/([^/?#]+)")


def _category_id(url: object) -> str | None:
    if not isinstance(url, str):
        return None
    match = _CATEGORY_ID_RE.search(url)
    return match.group(1) if match else None


def _shape_category(category: object) -> dict[str, object]:
    if not isinstance(category, dict):
        raise ValueError("Expected category to be an object")

    descendants = category.get("descendants") or []
    if not isinstance(descendants, list):
        raise ValueError("Expected category descendants to be a list")

    name = category.get("name")
    url = category.get("url")
    icon_url = category.get("iconUrl")
    if not isinstance(name, str):
        raise ValueError("Expected category name to be a string")
    if not isinstance(url, str):
        raise ValueError("Expected category url to be a string")
    if icon_url is not None and not isinstance(icon_url, str):
        raise ValueError("Expected category iconUrl to be a string or null")

    return {
        "id": _category_id(url),
        "name": name,
        "url": url,
        "icon_url": icon_url,
        "children": [_shape_category(child) for child in descendants],
    }


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get("response")
    if not isinstance(response, dict):
        raise ValueError("Missing response context")

    body = response.get("body")
    if not isinstance(body, str):
        raise ValueError("Expected JSON response body")

    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("Expected response JSON object")

    categories = payload.get("categories")
    if not isinstance(categories, list):
        raise ValueError("Expected categories to be a list")

    shaped = [_shape_category(category) for category in categories]
    context["output"] = {
        "count": len(shaped),
        "categories": shaped,
    }
    return context
