"""Output shaping for wallet balance."""

from __future__ import annotations

import json


def _money_value(payload: dict[str, object], key: str) -> int | float:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f'Expected {key} to be a number')
    return value


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

    if payload.get('message') == 'cart_not_found':
        context['output'] = {
            'usable': False,
            'available_balance': None,
            'applied_balance': None,
            'max_spendable_amount': None,
            'currency': 'EUR',
            'cart_required': True,
            'message': 'cart_not_found',
        }
        return context

    is_usable = payload.get('isUsable')
    if not isinstance(is_usable, bool):
        raise ValueError('Expected isUsable to be a boolean')

    context['output'] = {
        'usable': is_usable,
        'available_balance': _money_value(payload, 'availableBalance'),
        'applied_balance': _money_value(payload, 'appliedBalance'),
        'max_spendable_amount': _money_value(payload, 'maxSpendableAmount'),
        'currency': 'EUR',
        'cart_required': False,
        'message': None,
    }
    return context
