"""Output shaping for products list."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

_PRICE_PER_RE = re.compile(r'Price per unit:\s*([0-9]+(?:,[0-9]+)?)\s*€/([^\\s]+)')


class ProductCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.products: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None
        self._div_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name: value for name, value in attrs}
        if tag == 'div' and attr.get('data-product-code'):
            self._start_product(attr)
            return

        if self._current is None:
            return

        if tag == 'div':
            self._div_depth += 1
        if tag == 'a' and self._current.get('url') is None and attr.get('href'):
            self._current['url'] = attr['href']
        elif tag == 'img':
            self._set_image_url(attr.get('data-src') or attr.get('src'))
        elif tag == 'div' and (attr.get('aria-label') or '').endswith(' per pcs.'):
            self._current['price_label'] = attr['aria-label']
        elif tag == 'p' and (attr.get('aria-label') or '').startswith('Price per unit:'):
            self._set_unit_price(attr['aria-label'])

    def handle_endtag(self, tag: str) -> None:
        if self._current is None or tag != 'div':
            return
        self._div_depth -= 1
        if self._div_depth <= 0:
            self.products.append(self._current)
            self._current = None
            self._div_depth = 0

    def _start_product(self, attrs: dict[str, str | None]) -> None:
        raw = attrs.get('data-gtm-eec-product')
        payload: dict[str, object] = {}
        if raw:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                payload = loaded
        self._current = {
            'id': str(payload.get('id') or attrs['data-product-code']),
            'name': payload.get('name') or attrs.get('data-gtms-banner-title'),
            'category_id': payload.get('category'),
            'brand': payload.get('brand'),
            'price': payload.get('price'),
            'currency': payload.get('currency') or 'EUR',
            'url': None,
            'image_url': None,
            'unit_price': None,
        }
        self._div_depth = 1

    def _set_unit_price(self, label: str) -> None:
        if self._current is None:
            return
        match = _PRICE_PER_RE.search(label)
        if not match:
            self._current['unit_price'] = {'formatted': label.removeprefix('Price per unit:').strip()}
            return
        amount_text, unit = match.groups()
        self._current['unit_price'] = {
            'amount': float(amount_text.replace(',', '.')),
            'unit': unit,
            'formatted': f'{amount_text} €/{unit}',
        }

    def _set_image_url(self, candidate: str | None) -> None:
        if self._current is None or not candidate:
            return
        existing = self._current.get('image_url')
        if existing is None or 'cloudinary.com' in candidate:
            self._current['image_url'] = candidate


def _parse_products(html: str) -> list[dict[str, object]]:
    parser = ProductCardParser()
    parser.feed(html)
    parser.close()
    return parser.products


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get('response')
    args = context.get('args')
    if not isinstance(response, dict) or not isinstance(args, dict):
        raise ValueError('Missing processor context')

    body = response.get('body')
    if not isinstance(body, str):
        raise ValueError('Expected JSON response body')

    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError('Expected response JSON object')

    products_html = payload.get('products')
    if products_html is None and isinstance(payload.get('message'), str):
        context['output'] = {
            'available': False,
            'message': payload.get('message') or 'not_found',
            'category_id': args.get('category_id'),
            'page': args.get('page'),
            'page_size': args.get('page_size'),
            'sort': args.get('sort'),
            'count': 0,
            'search_url': payload.get('searchUrl'),
            'products': [],
        }
        return context
    if not isinstance(products_html, str):
        raise ValueError('Expected products HTML in response')

    products = _parse_products(products_html)
    context['output'] = {
        'available': True,
        'message': None,
        'category_id': args.get('category_id'),
        'page': args.get('page'),
        'page_size': args.get('page_size'),
        'sort': args.get('sort'),
        'count': len(products),
        'search_url': payload.get('searchUrl'),
        'products': products,
    }
    return context
