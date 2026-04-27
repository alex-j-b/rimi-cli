"""Output shaping for cart show."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

_WHITESPACE_RE = re.compile(r'\s+')
_MONEY_RE = re.compile(r'(-?\d+(?:[,.]\d+)?)\s*€')
_UNIT_PRICE_RE = re.compile(r'(-?\d+(?:[,.]\d+)?)\s*€/([^\s]+)')


def _class_contains(attrs: dict[str, str | None], class_name: str) -> bool:
    return class_name in (attrs.get('class') or '').split()


def _clean_text(value: str) -> str:
    return _WHITESPACE_RE.sub(' ', value).strip()


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


def _money_value(formatted: str | None) -> dict[str, object] | None:
    if not formatted:
        return None
    cleaned = _clean_text(formatted)
    match = _MONEY_RE.search(cleaned)
    return {
        'amount': _to_number(match.group(1)) if match else None,
        'formatted': cleaned,
        'currency': 'EUR' if '€' in cleaned else None,
    }


def _unit_price_value(formatted: str | None) -> dict[str, object] | None:
    if not formatted:
        return None
    cleaned = _clean_text(formatted)
    match = _UNIT_PRICE_RE.search(cleaned)
    if not match:
        return {'amount': None, 'unit': None, 'formatted': cleaned}
    amount, unit = match.groups()
    return {
        'amount': _to_number(amount),
        'unit': unit,
        'formatted': f'{amount} €/{unit}',
    }


class CartParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, object]] = []
        self.summary: list[dict[str, object]] = []
        self.empty = False
        self.checkout_enabled = None

        self._current: dict[str, object] | None = None
        self._current_depth = 0
        self._capture: str | None = None
        self._capture_chunks: list[str] = []

        self._summary_depth = 0
        self._row_depth = 0
        self._row_spans: list[str] = []
        self._span_depth = 0

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {name: value for name, value in attrs_list}

        if attrs.get('data-side-cart-empty') is not None:
            self.empty = True

        if tag == 'button' and attrs.get('data-side-cart-checkout-button') is not None:
            self.checkout_enabled = 'disabled' not in attrs and attrs.get('aria-disabled') != 'true'

        if tag == 'div' and _class_contains(attrs, 'side-cart__summary'):
            self._summary_depth = 1
            return

        if self._summary_depth:
            if tag == 'div':
                self._summary_depth += 1
                if self._row_depth:
                    self._row_depth += 1
                elif _class_contains(attrs, 'row'):
                    self._row_depth = 1
                    self._row_spans = []
            elif self._row_depth and tag == 'span':
                self._span_depth = 1
                self._capture = 'summary_span'
                self._capture_chunks = []
            elif self._span_depth:
                self._span_depth += 1

        if tag == 'div' and attrs.get('data-product-code'):
            self._start_item(attrs)
            return

        if self._current is None:
            return

        if tag == 'div':
            self._current_depth += 1
        elif tag == 'a' and _class_contains(attrs, 'side-card__name') and attrs.get('href'):
            self._current['url'] = attrs['href']
        elif tag == 'img':
            self._set_image_url(attrs.get('data-src') or attrs.get('src'))
        elif tag == 'input':
            self._capture_input(attrs)
        elif tag == 'p' and _class_contains(attrs, 'side-card__price-per'):
            self._capture = 'unit_price'
            self._capture_chunks = []
        elif tag == 'span' and (attrs.get('id') or '').startswith('cart-entry-price-'):
            self._capture = 'line_price'
            self._capture_chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._capture_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == 'summary_span' and tag == 'span':
            text = _clean_text(''.join(self._capture_chunks))
            if text:
                self._row_spans.append(text)
            self._capture = None
            self._capture_chunks = []

        if self._capture in {'unit_price', 'line_price'} and tag in {'p', 'span'}:
            text = _clean_text(''.join(self._capture_chunks))
            if self._current is not None:
                if self._capture == 'unit_price':
                    self._current['unit_price'] = _unit_price_value(text)
                else:
                    self._current['line_price'] = _money_value(text)
            self._capture = None
            self._capture_chunks = []

        if self._span_depth:
            self._span_depth -= 1

        if self._row_depth and tag == 'div':
            self._row_depth -= 1
            if self._row_depth == 0:
                self._append_summary_row()

        if self._summary_depth and tag == 'div':
            self._summary_depth -= 1

        if self._current is not None and tag == 'div':
            self._current_depth -= 1
            if self._current_depth <= 0:
                self.items.append(self._finalize_item(self._current))
                self._current = None
                self._current_depth = 0

    def _start_item(self, attrs: dict[str, str | None]) -> None:
        payload = _load_item_payload(attrs.get('data-gtm-eec-product'))
        self._current = {
            'id': str(payload.get('id') or attrs['data-product-code']),
            'name': payload.get('name') or attrs.get('data-gtm-click-name'),
            'category_id': payload.get('category'),
            'brand': payload.get('brand'),
            'quantity': _to_number(payload.get('quantity')),
            'unit': None,
            'step': None,
            'max_quantity': None,
            'line_price': _money_from_payload(payload.get('price'), payload.get('currency')),
            'unit_price': None,
            'url': None,
            'image_url': None,
        }
        self._current_depth = 1

    def _capture_input(self, attrs: dict[str, str | None]) -> None:
        if self._current is None:
            return
        name = attrs.get('name')
        if name == 'step':
            self._current['step'] = _to_number(attrs.get('value'))
        elif name == 'amount':
            self._current['quantity'] = _to_number(attrs.get('value') or attrs.get('data-amount'))
            self._current['unit'] = attrs.get('data-unit')
            self._current['max_quantity'] = _to_number(attrs.get('max'))

    def _set_image_url(self, candidate: str | None) -> None:
        if self._current is None or not candidate:
            return
        existing = self._current.get('image_url')
        if existing is None or 'q_auto' in candidate:
            self._current['image_url'] = candidate

    def _append_summary_row(self) -> None:
        if len(self._row_spans) < 2:
            return
        label = self._row_spans[0]
        value = self._row_spans[-1]
        self.summary.append({'label': label, **(_money_value(value) or {'formatted': value})})
        self._row_spans = []

    def _finalize_item(self, item: dict[str, object]) -> dict[str, object]:
        return {
            'id': item.get('id'),
            'name': item.get('name'),
            'category_id': item.get('category_id'),
            'brand': item.get('brand'),
            'quantity': item.get('quantity'),
            'unit': item.get('unit'),
            'step': item.get('step'),
            'max_quantity': item.get('max_quantity'),
            'line_price': item.get('line_price'),
            'unit_price': item.get('unit_price'),
            'url': item.get('url'),
            'image_url': item.get('image_url'),
        }


class HeaderParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.badge_count: int | float | None = None
        self.total: dict[str, object] | None = None
        self._capture: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {name: value for name, value in attrs_list}
        if tag == 'div' and _class_contains(attrs, 'badge'):
            self._capture = 'badge'
            self._chunks = []
        elif tag == 'span' and _class_contains(attrs, 'total-price'):
            self._capture = 'total'
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == 'badge' and tag == 'div':
            self.badge_count = _to_number(_clean_text(''.join(self._chunks)))
            self._capture = None
            self._chunks = []
        elif self._capture == 'total' and tag == 'span':
            self.total = _money_value(_clean_text(''.join(self._chunks)))
            self._capture = None
            self._chunks = []


def _load_item_payload(raw: str | None) -> dict[str, object]:
    if not raw:
        return {}
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _money_from_payload(amount: object, currency: object) -> dict[str, object] | None:
    number = _to_number(amount)
    if number is None:
        return None
    return {
        'amount': number,
        'formatted': f'{number:.2f} €' if isinstance(number, float) else f'{number} €',
        'currency': currency if isinstance(currency, str) else 'EUR',
    }


def _parse_side_cart(html: str) -> CartParser:
    parser = CartParser()
    parser.feed(html)
    parser.close()
    return parser


def _parse_header_cart(html: str | None) -> HeaderParser:
    parser = HeaderParser()
    if html:
        parser.feed(html)
        parser.close()
    return parser


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

    message = payload.get('message')
    if isinstance(message, str):
        context['output'] = {
            'available': False,
            'message': message,
            'empty': True,
            'count': 0,
            'badge_count': None,
            'currency': 'EUR',
            'total': None,
            'summary': [],
            'minimum_order_warning': False,
            'show_configure_delivery_popup': bool(payload.get('showConfigureDeliveryPopup')),
            'checkout_enabled': False,
            'items': [],
        }
        return context

    side_cart = payload.get('sideCart')
    if not isinstance(side_cart, str):
        raise ValueError('Expected sideCart HTML in response')

    cart = _parse_side_cart(side_cart)
    header = _parse_header_cart(payload.get('headerCart') if isinstance(payload.get('headerCart'), str) else None)
    total = header.total or next((row for row in cart.summary if row.get('label') == 'Total'), None)

    context['output'] = {
        'available': True,
        'message': None,
        'empty': cart.empty or not cart.items,
        'count': len(cart.items),
        'badge_count': header.badge_count,
        'currency': 'EUR',
        'total': total,
        'summary': cart.summary,
        'minimum_order_warning': '-show-min-warning' in side_cart,
        'show_configure_delivery_popup': bool(payload.get('showConfigureDeliveryPopup')),
        'checkout_enabled': bool(cart.checkout_enabled),
        'items': cart.items,
    }
    return context
