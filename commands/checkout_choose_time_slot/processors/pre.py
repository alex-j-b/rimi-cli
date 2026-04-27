"""Request preparation for checkout choose-time-slot."""

from __future__ import annotations


def run(context: dict[str, object]) -> dict[str, object]:
    request = context.get('request')
    if not isinstance(request, dict):
        raise ValueError('Missing request context')

    body = request.get('body')
    if not isinstance(body, dict):
        raise ValueError('Expected request body to be an object')

    time_id = body.get('time_id')
    if not isinstance(time_id, str) or not time_id.strip():
        raise ValueError('Expected time_id to be a non-empty string')
    body['time_id'] = time_id.strip()

    headers = request.setdefault('headers', {})
    if not isinstance(headers, dict):
        raise ValueError('Expected request headers to be an object')
    headers['accept'] = 'application/json'
    headers['content-type'] = 'application/x-www-form-urlencoded'
    headers['origin'] = 'https://www.rimi.ee'
    headers['referer'] = 'https://www.rimi.ee/epood/en/checkout/delivery/collect/time-slots'
    headers.pop('content-length', None)
    return context
