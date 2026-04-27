"""Output shaping for favorites categories."""

from __future__ import annotations

import json


def _category(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError('Expected category object')
    code = raw.get('code')
    name = raw.get('name')
    item_count = raw.get('itemCount')
    products_url = raw.get('productsUrl')
    if not isinstance(code, str) or not isinstance(name, str):
        raise ValueError('Expected category code and name')
    if not isinstance(item_count, int):
        raise ValueError('Expected category itemCount')
    if not isinstance(products_url, str):
        raise ValueError('Expected category productsUrl')
    return {
        'id': code,
        'name': name.strip(),
        'item_count': item_count,
        'products_url': products_url,
    }


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get('response')
    if not isinstance(response, dict):
        raise ValueError('Missing response context')

    body = response.get('body')
    if not isinstance(body, str):
        raise ValueError('Expected JSON response body')

    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError('Expected response JSON object')

    categories_raw = payload.get('categories')
    if not isinstance(categories_raw, list):
        raise ValueError('Expected categories list')

    categories = [_category(category) for category in categories_raw]
    context['output'] = {
        'count': len(categories),
        'categories': categories,
    }
    return context
