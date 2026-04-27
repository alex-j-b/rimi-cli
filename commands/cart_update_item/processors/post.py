"""Output shaping for cart update-item."""

from __future__ import annotations

import json


def _quantity_value(value: object) -> object:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get('response')
    args = context.get('args')
    if not isinstance(response, dict) or not isinstance(args, dict):
        raise ValueError('Missing processor context')

    body = response.get('body')
    if not isinstance(body, str):
        raise ValueError('Expected JSON response body')

    payload = json.loads(body)
    if isinstance(payload, dict) and isinstance(payload.get('message'), str):
        context['output'] = {
            'updated': False,
            'product_id': str(args.get('product_id')),
            'quantity': _quantity_value(args.get('quantity')),
            'message': payload['message'],
        }
        return context

    context['output'] = {
        'updated': 200 <= int(response.get('status', 0)) < 300,
        'product_id': str(args.get('product_id')),
        'quantity': _quantity_value(args.get('quantity')),
        'message': None,
    }
    return context
