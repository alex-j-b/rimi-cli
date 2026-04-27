"""Output shaping for account whoami."""

from __future__ import annotations

import json


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

    user_name = payload.get('userName')
    if user_name is not None and not isinstance(user_name, str):
        raise ValueError('Expected userName to be a string')

    context['output'] = {
        'user_name': user_name,
        'signed_in': bool(user_name),
    }
    return context
