"""Output shaping for order invoice details."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

BASE_URL = 'https://www.rimi.ee'
VOID_TAGS = {
    'area',
    'base',
    'br',
    'circle',
    'col',
    'embed',
    'hr',
    'img',
    'input',
    'link',
    'meta',
    'param',
    'path',
    'source',
    'track',
    'wbr',
}


def _class_contains(attrs: dict[str, str | None], name: str) -> bool:
    return name in (attrs.get('class') or '').split()


def _clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip()


def _parse_money_cents(value: str | None) -> int | None:
    if not value:
        return None
    raw = value.replace('\xa0', ' ')
    decimal_text = raw.replace('€', '').strip().replace(' ', '').replace(',', '.')
    if re.fullmatch(r'\d+\.\d{1,2}', decimal_text):
        amount_text = decimal_text
    else:
        parts = re.findall(r'\d+', raw)
        if len(parts) >= 2:
            amount_text = f'{parts[0]}.{parts[1][:2]}'
        elif len(parts) == 1:
            amount_text = parts[0]
        else:
            return None
    try:
        amount = Decimal(amount_text)
    except Exception:
        return None
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _money_from_cents(cents: int | None) -> float | None:
    if cents is None:
        return None
    return float((Decimal(cents) / Decimal(100)).quantize(Decimal('0.01')))


def _parse_quantity(value: str | None) -> tuple[float | None, str | None, str | None]:
    if not value:
        return None, None, None
    cleaned = _clean_text(value.replace('Product quantity input field name:', ''))
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*(.*)', cleaned)
    if not match:
        return None, None, cleaned
    unit = match.group(2).strip() or None
    return float(match.group(1)), unit, cleaned


class OrderInvoiceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.order_id: str | None = None
        self.info: dict[str, str] = {}
        self.products: list[dict[str, Any]] = []
        self.current_category: str | None = None
        self._class_stack: list[set[str]] = []
        self._capture: str | None = None
        self._capture_text: list[str] = []
        self._pending_label: str | None = None
        self._product: dict[str, Any] | None = None
        self._product_depth = 0
        self._price_depth = 0
        self._price_text: list[str] = []
        self._in_script_or_style = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs_list)
        classes = set((attrs.get('class') or '').split())
        self._class_stack.append(classes)

        if tag in {'script', 'style'}:
            self._in_script_or_style = True
            return

        if tag == 'div' and _class_contains(attrs, 'order-card'):
            self._product = {'category': self.current_category}
            self._product_depth = 1
            return
        if self._product is not None:
            self._handle_product_start(tag, attrs)
            if tag in VOID_TAGS and self._class_stack:
                self._class_stack.pop()
            return

        if tag == 'h2' and _class_contains(attrs, 'modal__heading'):
            self._start_capture('heading')
        elif tag == 'span' and self._inside('categories__title'):
            self._start_capture('category')
        elif tag == 'span' and self._inside('item__name'):
            self._start_capture('info_label')
        elif tag == 'span' and self._inside('item__value'):
            self._start_capture('info_value')
        if tag in VOID_TAGS and self._class_stack:
            self._class_stack.pop()

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        if tag in VOID_TAGS:
            self.handle_starttag(tag, attrs_list)
            return
        self.handle_starttag(tag, attrs_list)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in {'script', 'style'}:
            self._in_script_or_style = False

        if self._product is not None:
            self._handle_product_end()
        elif self._capture is not None:
            self._finish_capture()

        if self._class_stack:
            self._class_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_script_or_style:
            return
        if self._product is not None and self._price_depth:
            self._price_text.append(data)
        if self._capture is not None:
            self._capture_text.append(data)

    def _inside(self, class_name: str) -> bool:
        return any(class_name in classes for classes in self._class_stack)

    def _start_capture(self, name: str) -> None:
        self._capture = name
        self._capture_text = []

    def _finish_capture(self) -> None:
        capture = self._capture
        text = _clean_text(' '.join(self._capture_text))
        self._capture = None
        self._capture_text = []
        if not text:
            return
        if capture == 'heading':
            match = re.search(r'Order\s+(\d+)', text)
            self.order_id = match.group(1) if match else text
        elif capture == 'category':
            self.current_category = text
        elif capture == 'info_label':
            self._pending_label = text.rstrip(':')
        elif capture == 'info_value' and self._pending_label:
            self.info[self._pending_label] = text
            self._pending_label = None

    def _handle_product_start(self, tag: str, attrs: dict[str, str | None]) -> None:
        if tag not in VOID_TAGS:
            self._product_depth += 1
        if self._price_depth and not (tag == 'div' and _class_contains(attrs, 'order-card__price')):
            self._price_depth += 1
        if tag == 'a' and self._inside('order-card__name') and not self._product.get('name'):
            href = attrs.get('href')
            self._product['url'] = urljoin(BASE_URL, href) if href else None
            self._start_capture('product_name')
        elif tag == 'span' and attrs.get('id', '').startswith('cart-entry-amount-'):
            self._start_capture('quantity')
        elif tag == 'div' and _class_contains(attrs, 'order-card__price'):
            self._price_depth = 1
            self._price_text = []

    def _handle_product_end(self) -> None:
        if self._capture is not None:
            capture = self._capture
            text = _clean_text(' '.join(self._capture_text))
            self._capture = None
            self._capture_text = []
            if capture == 'product_name':
                self._product['name'] = text
                product_id = self._product.get('url', '').rstrip('/').split('/')[-1]
                self._product['product_id'] = product_id or None
            elif capture == 'quantity':
                quantity, unit, raw = _parse_quantity(text)
                self._product['quantity'] = quantity
                self._product['quantity_unit'] = unit
                self._product['quantity_text'] = raw

        if self._price_depth:
            self._price_depth -= 1
            if self._price_depth == 0:
                price_text = _clean_text(' '.join(self._price_text))
                price_cents = _parse_money_cents(price_text)
                self._product['total_price'] = _money_from_cents(price_cents)
                self._product['total_price_cents'] = price_cents
                self._product['currency'] = 'EUR' if price_cents is not None else None
                self._price_text = []

        self._product_depth -= 1
        if self._product_depth <= 0:
            if self._product.get('name'):
                self.products.append(self._product)
            self._product = None


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get('response', {})
    status = response.get('status') if isinstance(response, dict) else None
    if isinstance(status, int) and status >= 400:
        raise ValueError(f'Order invoice request failed with HTTP {status}')

    body = response.get('body') if isinstance(response, dict) else None
    if not isinstance(body, str):
        raise ValueError('Expected order invoice response body to be text/html')

    parser = OrderInvoiceParser()
    parser.feed(body)

    total_cents = _parse_money_cents(parser.info.get('Total sum'))
    refund_cents = _parse_money_cents(parser.info.get('Refund'))
    deposit_fee_cents = _parse_money_cents(parser.info.get('Deposit fee'))
    packing_fee_cents = _parse_money_cents(parser.info.get('Packing fee'))
    delivery_fee_cents = _parse_money_cents(parser.info.get('Delivery fee'))

    requested_order_id = (context.get('args') or {}).get('order_id') if isinstance(context.get('args'), dict) else None
    order_id = parser.order_id or (str(requested_order_id) if requested_order_id else None)
    if not order_id:
        raise ValueError('Could not find order details in the response')
    if requested_order_id and parser.order_id and str(requested_order_id) != parser.order_id:
        raise ValueError(f'Response order id {parser.order_id} did not match requested order id {requested_order_id}')
    if not parser.products:
        raise ValueError('Could not find purchased products in the order response')

    context['output'] = {
        'order_id': order_id,
        'order_time': parser.info.get('Order time'),
        'pickup_time': parser.info.get('Pickup time'),
        'pickup_address': parser.info.get('Pickup address'),
        'rimi_money_earned': parser.info.get('Rimi money earned'),
        'totals': {
            'total': _money_from_cents(total_cents),
            'total_cents': total_cents,
            'deposit_fee': _money_from_cents(deposit_fee_cents),
            'deposit_fee_cents': deposit_fee_cents,
            'packing_fee': _money_from_cents(packing_fee_cents),
            'packing_fee_cents': packing_fee_cents,
            'delivery_fee': _money_from_cents(delivery_fee_cents),
            'delivery_fee_cents': delivery_fee_cents,
            'refund': _money_from_cents(refund_cents),
            'refund_cents': refund_cents,
            'currency': 'EUR',
        },
        'products': parser.products,
        'product_count': len(parser.products),
    }
    return context
