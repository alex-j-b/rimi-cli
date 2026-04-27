"""Request preparation for products list."""

from __future__ import annotations


def run(context: dict[str, object]) -> dict[str, object]:
    args = context.get('args')
    request = context.get('request')
    if not isinstance(args, dict) or not isinstance(request, dict):
        raise ValueError('Missing processor context')

    category_id = args.get('category_id')
    sort = args.get('sort')
    if not isinstance(category_id, str):
        raise ValueError('Expected category_id to be a string')
    if not isinstance(sort, str):
        raise ValueError('Expected sort to be a string')

    path = f'/epood/en/products/c/{category_id}'
    request['path_template'] = path
    request['url_template'] = f'https://www.rimi.ee{path}'
    request['path'] = path
    request['url'] = f'https://www.rimi.ee{path}'

    query = request.setdefault('query', {})
    if not isinstance(query, dict):
        raise ValueError('Expected request query to be an object')
    query['query'] = f':{sort}:allCategories:{category_id}:assortmentStatus:inAssortment'

    headers = request.setdefault('headers', {})
    if not isinstance(headers, dict):
        raise ValueError('Expected request headers to be an object')
    headers['accept'] = 'application/json'
    headers['x-requested-with'] = 'XMLHttpRequest'
    headers['referer'] = f'https://www.rimi.ee{path}'
    return context
