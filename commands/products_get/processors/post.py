"""Output shaping for product details."""

from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser

_UNIT_PRICE_RE = re.compile(r'([0-9]+(?:[,.][0-9]+)?)\s*€\s*/\s*([^\s]+)')
_WHITESPACE_RE = re.compile(r'\s+')


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str | None:
        value = _WHITESPACE_RE.sub(' ', ' '.join(self.parts)).strip()
        return value or None


class ProductPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.structured_data_text = ''
        self.categories: list[dict[str, str | None]] = []
        self.unit_price: dict[str, object] | None = None
        self.favorite: bool | None = None
        self.cart: dict[str, object] | None = None
        self.image_url: str | None = None

        self._in_ld_json = False
        self._in_breadcrumb_nav = False
        self._breadcrumb_link: dict[str, str | None] | None = None
        self._breadcrumb_text: list[str] = []
        self._in_price_per = False
        self._price_per_text: list[str] = []
        self._in_counter_form = False
        self._pending_cart: dict[str, object] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name: value for name, value in attrs}
        classes = set((attr.get('class') or '').split())

        if tag == 'script' and attr.get('type') == 'application/ld+json':
            self._in_ld_json = True
            return
        if tag == 'nav' and attr.get('aria-label') == 'Breadcrumb navigation':
            self._in_breadcrumb_nav = True
            return
        if self._in_breadcrumb_nav and tag == 'a':
            self._breadcrumb_link = {'url': attr.get('href')}
            self._breadcrumb_text = []
            return
        if tag == 'p' and 'price-per' in classes:
            self._in_price_per = True
            self._price_per_text = []
            return
        if tag == 'img' and attr.get('data-src') and self.image_url is None:
            self.image_url = attr['data-src']
        if tag == 'form' and 'favorite' in classes:
            self.favorite = '-checked' in classes
        if tag == 'form' and 'counter' in classes:
            self._in_counter_form = True
            self._pending_cart = {}
        if self._in_counter_form and tag == 'input':
            self._capture_cart_input(attr)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script':
            self._in_ld_json = False
        elif tag == 'nav':
            self._in_breadcrumb_nav = False
        elif self._in_breadcrumb_nav and tag == 'a' and self._breadcrumb_link is not None:
            name = _clean_text(' '.join(self._breadcrumb_text))
            if name:
                self._breadcrumb_link['name'] = name
                self._breadcrumb_link['id'] = _category_id_from_url(self._breadcrumb_link.get('url'))
                self.categories.append(self._breadcrumb_link)
            self._breadcrumb_link = None
            self._breadcrumb_text = []
        elif tag == 'p' and self._in_price_per:
            self.unit_price = _parse_unit_price(' '.join(self._price_per_text))
            self._in_price_per = False
            self._price_per_text = []
        elif tag == 'form' and self._in_counter_form:
            self.cart = self._finalize_cart(self._pending_cart)
            self._in_counter_form = False
            self._pending_cart = {}

    def handle_data(self, data: str) -> None:
        if self._in_ld_json:
            self.structured_data_text += data
        if self._breadcrumb_link is not None:
            self._breadcrumb_text.append(data)
        if self._in_price_per:
            self._price_per_text.append(data)

    def _capture_cart_input(self, attr: dict[str, str | None]) -> None:
        name = attr.get('name')
        if name == 'amount':
            self._pending_cart['quantity'] = _to_number(attr.get('value'))
            if attr.get('max'):
                self._pending_cart['max_quantity'] = _to_number(attr.get('max'))
            if attr.get('data-unit'):
                self._pending_cart['unit'] = attr['data-unit']
        elif name == 'step':
            self._pending_cart['step'] = _to_number(attr.get('value'))

    def _finalize_cart(self, cart: dict[str, object]) -> dict[str, object] | None:
        if not cart:
            return None
        return {
            'quantity': cart.get('quantity'),
            'unit': cart.get('unit'),
            'step': cart.get('step'),
            'max_quantity': cart.get('max_quantity'),
        }


class NutritionTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []

        self._in_row = False
        self._in_cell = False
        self._current_row: list[str] = []
        self._current_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'tr':
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in {'th', 'td'}:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if self._in_cell and tag in {'th', 'td'}:
            value = _clean_text(' '.join(self._current_cell))
            if value:
                self._current_row.append(value)
            self._in_cell = False
            self._current_cell = []
        elif self._in_row and tag == 'tr':
            if self._current_row:
                self.rows.append(self._current_row)
            self._in_row = False
            self._current_row = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _WHITESPACE_RE.sub(' ', unescape(value)).strip()
    return cleaned or None


def _strip_html(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    parser = TextExtractor()
    parser.feed(cleaned)
    parser.close()
    return parser.text() or cleaned


def _category_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r'/c/([^/?#]+)', url)
    return match.group(1) if match else None


def _parse_unit_price(value: str) -> dict[str, object] | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    match = _UNIT_PRICE_RE.search(cleaned)
    if not match:
        return {'formatted': cleaned}
    amount_text, unit = match.groups()
    return {
        'amount': float(amount_text.replace(',', '.')),
        'unit': unit,
        'formatted': f'{amount_text} €/{unit}',
    }


def _to_number(value: str | None) -> int | float | None:
    if value is None or value == '':
        return None
    normalized = value.replace(',', '.')
    number = float(normalized)
    return int(number) if number.is_integer() else number


def _loads_relaxed_json(value: str) -> dict[str, object]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        loaded = json.loads(_escape_control_chars_in_strings(value))
    if not isinstance(loaded, dict):
        raise ValueError('Expected product structured data object')
    return loaded


def _escape_control_chars_in_strings(value: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False
    for char in value:
        if in_string and char in {'\n', '\r', '\t'}:
            result.append({'\n': '\\n', '\r': '\\r', '\t': '\\t'}[char])
            escaped = False
            continue
        result.append(char)
        if escaped:
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == '"':
            in_string = not in_string
    return ''.join(result)


def _availability(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.rsplit('/', 1)[-1].replace('InStock', 'in_stock').replace('OutOfStock', 'out_of_stock')


def _extract_details_html(page_html: str) -> str | None:
    match = re.search(r"identifier:\s*'details'.*?html:\s*\"((?:\\.|[^\"\\])*)\"", page_html, re.S)
    if not match:
        return None
    try:
        decoded = json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, str) else None


def _parse_nutrition(page_html: str) -> dict[str, object] | None:
    details_html = _extract_details_html(page_html)
    if not details_html or 'Nutrition Facts' not in details_html:
        return None

    table = NutritionTableParser()
    table.feed(details_html)
    table.close()

    rows = [row for row in table.rows if len(row) >= 2]
    if not rows or rows[0][0].lower() != 'nutrition':
        return None

    serving = rows[0][1]
    values = [{'name': row[0], 'value': row[1]} for row in rows[1:]]
    return {
        'basis': serving,
        'values': values,
    }


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get('response')
    args = context.get('args')
    if not isinstance(response, dict) or not isinstance(args, dict):
        raise ValueError('Missing processor context')

    body = response.get('body')
    if not isinstance(body, str):
        raise ValueError('Expected HTML response body')

    if response.get('status') == 404:
        context['output'] = {
            'available': False,
            'message': 'not_found',
            'id': args.get('product_id'),
            'product': None,
        }
        return context

    parser = ProductPageParser()
    parser.feed(body)
    parser.close()

    product = _loads_relaxed_json(parser.structured_data_text)
    offer = product.get('offers') if isinstance(product.get('offers'), dict) else {}
    image = product.get('image')
    image_url = image[0] if isinstance(image, list) and image else parser.image_url

    context['output'] = {
        'available': True,
        'message': None,
        'id': str(product.get('sku') or args.get('product_id')),
        'name': product.get('name'),
        'description': _strip_html(product.get('description') if isinstance(product.get('description'), str) else None),
        'price': _to_number(str(offer.get('price'))) if offer.get('price') is not None else None,
        'currency': offer.get('priceCurrency'),
        'unit_price': parser.unit_price,
        'nutrition': _parse_nutrition(body),
        'availability': _availability(offer.get('availability')),
        'url': offer.get('url'),
        'image_url': image_url,
        'categories': parser.categories,
        'favorite': parser.favorite,
        'cart': parser.cart,
    }
    return context
