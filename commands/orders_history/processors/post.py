"""Output shaping for order history."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import httpx

BASE_URL = 'https://www.rimi.ee'
COMPLETED_STATUS_FRAGMENT = 'completed'


def _class_contains(attrs: dict[str, str | None], name: str) -> bool:
    classes = attrs.get('class') or ''
    return name in classes.split()


def _clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip()


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4})', value.strip())
    if not match:
        return value.strip()
    day, month, year = match.groups()
    return f'{year}-{month}-{day}'


def _parse_money_cents(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.replace('\xa0', ' ').replace('€', '').strip()
    normalized = normalized.replace(' ', '').replace(',', '.')
    try:
        amount = Decimal(normalized)
    except Exception:
        return None
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _money_from_cents(cents: int | None) -> float | None:
    if cents is None:
        return None
    return float((Decimal(cents) / Decimal(100)).quantize(Decimal('0.01')))


class OrderHistoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.orders: list[dict[str, Any]] = []
        self.pages: set[int] = set()
        self._row: dict[str, Any] | None = None
        self._cell_text: list[str] | None = None
        self._cells: list[str] = []
        self._in_script_or_style = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs_list)
        if tag in {'script', 'style'}:
            self._in_script_or_style = True
            return
        if tag == 'tr' and _class_contains(attrs, 'order-table__row'):
            self._row = {
                'order_id': attrs.get('data-order'),
                'invoice_url': None,
                'view_url': None,
            }
            self._cells = []
            return
        if self._row is None:
            if tag == 'a':
                page = attrs.get('data-page')
                if page and page.isdigit():
                    self.pages.add(int(page))
            return
        if tag == 'td':
            self._cell_text = []
        elif tag == 'a' and attrs.get('href') and '/invoice' in attrs['href']:
            self._row['invoice_url'] = urljoin(BASE_URL, attrs['href'])
        elif tag == 'form' and attrs.get('action') and attrs.get('action', '').endswith('/view'):
            self._row['view_url'] = urljoin(BASE_URL, attrs['action'])

    def handle_endtag(self, tag: str) -> None:
        if tag in {'script', 'style'}:
            self._in_script_or_style = False
            return
        if self._row is None:
            return
        if tag == 'td' and self._cell_text is not None:
            self._cells.append(_clean_text(' '.join(self._cell_text)))
            self._cell_text = None
        elif tag == 'tr':
            self._finish_row()

    def handle_data(self, data: str) -> None:
        if self._in_script_or_style or self._cell_text is None:
            return
        self._cell_text.append(data)

    def _finish_row(self) -> None:
        if self._row is None:
            return
        cells = self._cells
        total_cents = _parse_money_cents(cells[1] if len(cells) > 1 else None)
        status = cells[3] if len(cells) > 3 else None
        order_id = self._row.get('order_id') or (cells[2] if len(cells) > 2 else None)
        self.orders.append(
            {
                'order_id': order_id,
                'date': _parse_date(cells[0] if cells else None),
                'total': _money_from_cents(total_cents),
                'total_cents': total_cents,
                'currency': 'EUR' if total_cents is not None else None,
                'status': status,
                'valid': bool(status and COMPLETED_STATUS_FRAGMENT in status.lower() and total_cents is not None),
                'invoice_url': self._row.get('invoice_url'),
                'view_url': self._row.get('view_url'),
            }
        )
        self._row = None
        self._cell_text = None
        self._cells = []


def _parse_page(html: str) -> tuple[list[dict[str, Any]], int | None]:
    parser = OrderHistoryParser()
    parser.feed(html)
    total_pages = max(parser.pages) if parser.pages else None
    return parser.orders, total_pages


def _fetch_page(context: dict[str, Any], page: int) -> str:
    request = context['request']
    query = dict(request.get('query') or {})
    query['currentPage'] = page
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.request(
            request['method'],
            request['url_template'],
            params=query,
            headers=dict(request.get('headers') or {}),
        )
    response.raise_for_status()
    return response.text


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get('response', {})
    status = response.get('status') if isinstance(response, dict) else None
    if isinstance(status, int) and status >= 400:
        raise ValueError(f'Order history request failed with HTTP {status}')

    body = response.get('body') if isinstance(response, dict) else None
    if not isinstance(body, str):
        raise ValueError('Expected order history response body to be text/html')

    orders, total_pages = _parse_page(body)
    pages_fetched = [1]
    fetched_complete_history = context.get('execution_mode') == 'live'

    if context.get('execution_mode') == 'live':
        total_pages = total_pages or 1
        by_id = {order.get('order_id'): order for order in orders}
        for next_page in range(1, total_pages + 1):
            if next_page == 1:
                continue
            next_orders, _ = _parse_page(_fetch_page(context, next_page))  # type: ignore[arg-type]
            pages_fetched.append(next_page)
            for order in next_orders:
                by_id[order.get('order_id')] = order
        orders = list(by_id.values())
        orders.sort(key=lambda order: (order.get('date') or '', order.get('order_id') or ''), reverse=True)

    context['output'] = {
        'orders': orders,
        'pagination': {
            'total_pages': total_pages,
            'pages_fetched': sorted(pages_fetched),
            'complete_history': fetched_complete_history,
        },
    }
    return context
