"""Output shaping for cart recommendations."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

_PRICE_PER_RE = re.compile(r'Price per unit:\s*([0-9]+(?:,[0-9]+)?)\s*€/([^\s]+)')


def _class_contains(attrs: dict[str, str | None], class_name: str) -> bool:
    return class_name in (attrs.get('class') or '').split()


def _to_number(value: object) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace(',', '.')
    if not normalized:
        return None
    try:
        number = float(normalized)
    except ValueError:
        return None
    if number.is_integer():
        return int(number)
    return number


class ProductCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.products: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None
        self._div_depth = 0

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {name: value for name, value in attrs_list}
        if tag == 'div' and attrs.get('data-product-code'):
            self._start_product(attrs)
            return

        if self._current is None:
            return

        if tag == 'div':
            self._div_depth += 1
            if _class_contains(attrs, 'card__price') and attrs.get('aria-label'):
                self._current['price_label'] = attrs['aria-label']
        elif tag == 'a' and _class_contains(attrs, 'card__url') and attrs.get('href'):
            self._current['url'] = attrs['href']
        elif tag == 'img':
            self._set_image_url(attrs)
        elif tag == 'p' and _class_contains(attrs, 'card__price-per') and attrs.get('aria-label'):
            self._set_unit_price(attrs['aria-label'])
        elif tag == 'form' and _class_contains(attrs, 'favorite'):
            self._current['favorite'] = _class_contains(attrs, '-checked')
        elif tag == 'input':
            self._capture_cart_input(attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None or tag != 'div':
            return
        self._div_depth -= 1
        if self._div_depth <= 0:
            self.products.append(self._finalize_product(self._current))
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
            'name': payload.get('name') or attrs.get('data-gtm-click-name'),
            'category_id': payload.get('category'),
            'brand': payload.get('brand'),
            'price': payload.get('price'),
            'currency': payload.get('currency') or 'EUR',
            'price_label': None,
            'unit_price': None,
            'favorite': False,
            'cart': {
                'quantity': None,
                'unit': None,
                'step': None,
                'max_quantity': None,
            },
            'url': None,
            'image_url': None,
        }
        self._div_depth = 1

    def _set_image_url(self, attrs: dict[str, str | None]) -> None:
        if self._current is None:
            return
        candidate = attrs.get('data-src') or attrs.get('src')
        if not candidate:
            return
        alt = attrs.get('alt')
        if self._current.get('image_url') is None or alt == self._current.get('name'):
            self._current['image_url'] = candidate

    def _set_unit_price(self, label: str) -> None:
        if self._current is None:
            return
        match = _PRICE_PER_RE.search(label)
        if not match:
            self._current['unit_price'] = {'formatted': label.removeprefix('Price per unit:').strip()}
            return
        amount_text, unit = match.groups()
        self._current['unit_price'] = {
            'amount': _to_number(amount_text),
            'unit': unit,
            'formatted': f'{amount_text} €/{unit}',
        }

    def _capture_cart_input(self, attrs: dict[str, str | None]) -> None:
        if self._current is None:
            return
        cart = self._current.get('cart')
        if not isinstance(cart, dict):
            return
        name = attrs.get('name')
        if name == 'step':
            cart['step'] = _to_number(attrs.get('value'))
        elif name == 'amount':
            cart['quantity'] = _to_number(attrs.get('value') or attrs.get('data-amount'))
            cart['unit'] = attrs.get('data-unit')
            cart['max_quantity'] = _to_number(attrs.get('max'))

    def _finalize_product(self, product: dict[str, object]) -> dict[str, object]:
        return {
            'id': product.get('id'),
            'name': product.get('name'),
            'category_id': product.get('category_id'),
            'brand': product.get('brand'),
            'price': product.get('price'),
            'currency': product.get('currency'),
            'price_label': product.get('price_label'),
            'unit_price': product.get('unit_price'),
            'favorite': product.get('favorite'),
            'cart': product.get('cart'),
            'url': product.get('url'),
            'image_url': product.get('image_url'),
        }


def _parse_products(html: str) -> list[dict[str, object]]:
    parser = ProductCardParser()
    parser.feed(html)
    parser.close()
    products: list[dict[str, object]] = []
    seen: set[str] = set()
    for product in parser.products:
        product_id = product.get('id')
        if not isinstance(product_id, str) or product_id in seen:
            continue
        seen.add(product_id)
        products.append(product)
    return products


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get('response')
    if not isinstance(response, dict):
        raise ValueError('Missing response context')

    body = response.get('body')
    if not isinstance(body, str):
        raise ValueError('Expected HTML response body')

    products = _parse_products(body)
    context['output'] = {
        'count': len(products),
        'products': products,
    }
    return context
