"""Output shaping for checkout time slots."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re


_WHITESPACE_RE = re.compile(r"\s+")
_AVAILABLE_COUNT_RE = re.compile(r"Available slots:\s*(\d+)", re.I)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", unescape(value)).strip()
    return cleaned or None


def _classes(attrs: dict[str, str | None]) -> set[str]:
    return set((attrs.get("class") or "").split())


def _to_price(value: str | None) -> float | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    match = re.search(r"([0-9]+(?:[,.][0-9]+)?)", cleaned)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


class TimeSlotsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.date_options: list[dict[str, object]] = []
        self.slots: list[dict[str, object]] = []

        self._current_date: dict[str, object] | None = None
        self._date_depth = 0
        self._in_date_label = False
        self._date_label_parts: list[str] = []

        self._current_slot: dict[str, object] | None = None
        self._slot_depth = 0
        self._in_availability = False
        self._availability_depth = 0
        self._availability_parts: list[str] = []
        self._in_price = False
        self._price_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {name: value for name, value in attrs_list}
        classes = _classes(attrs)

        if tag == "div" and "date-selector__item" in classes:
            self._current_date = {
                "date": None,
                "label": None,
                "display": None,
                "offset": attrs.get("data-gtm-click-name"),
                "selected": False,
            }
            self._date_depth = 1
            self._date_label_parts = []
            return

        if self._current_date is not None:
            if tag == "div":
                self._date_depth += 1
            elif tag == "input" and attrs.get("name") == "date":
                self._current_date["date"] = attrs.get("value")
                self._current_date["selected"] = "checked" in attrs
            elif tag == "label":
                self._in_date_label = True
                self._date_label_parts = []
            return

        if tag == "div" and "value" in classes and attrs.get("data-gtm-click-name"):
            self._current_slot = {
                "id": None,
                "time": attrs.get("data-gtm-click-name"),
                "available": True,
                "availability": None,
                "availability_code": None,
                "price": None,
                "currency": "EUR",
                "price_label": None,
            }
            self._slot_depth = 1
            return

        if self._current_slot is not None:
            if tag == "div":
                self._slot_depth += 1
                if self._in_availability:
                    self._availability_depth += 1
                if "value__availability" in classes:
                    self._in_availability = True
                    self._availability_depth = 1
                    self._availability_parts = []
                    for class_name in sorted(classes):
                        if class_name.startswith("-"):
                            self._current_slot["availability_code"] = class_name[1:].replace("-", "_")
            elif tag == "input" and attrs.get("name") == "time_id":
                self._current_slot["id"] = attrs.get("value")
                if "disabled" in attrs:
                    self._current_slot["available"] = False
            elif tag == "p" and "value__price" in classes:
                self._in_price = True
                self._price_parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._current_date is not None:
            if tag == "label" and self._in_date_label:
                label_parts = [_clean_text(part) for part in self._date_label_parts]
                label_parts = [part for part in label_parts if part]
                if label_parts:
                    self._current_date["label"] = label_parts[0]
                    self._current_date["display"] = label_parts[-1]
                self._in_date_label = False
                self._date_label_parts = []
            elif tag == "div":
                self._date_depth -= 1
                if self._date_depth <= 0:
                    if self._current_date.get("date"):
                        self.date_options.append(self._current_date)
                    self._current_date = None
                    self._date_depth = 0
            return

        if self._current_slot is None:
            return

        if tag == "div" and self._in_availability:
            self._availability_depth -= 1
            if self._availability_depth <= 0:
                availability = _clean_text(" ".join(self._availability_parts))
                self._current_slot["availability"] = availability
                if availability and availability.lower() == "unavailable":
                    self._current_slot["available"] = False
                self._in_availability = False
                self._availability_depth = 0
                self._availability_parts = []

        if tag == "p" and self._in_price:
            price_label = _clean_text(" ".join(self._price_parts))
            self._current_slot["price_label"] = price_label
            self._current_slot["price"] = _to_price(price_label)
            self._in_price = False
            self._price_parts = []
            return

        if tag == "div":
            self._slot_depth -= 1
            if self._slot_depth <= 0:
                if self._current_slot.get("id"):
                    self.slots.append(self._current_slot)
                self._current_slot = None
                self._slot_depth = 0

    def handle_data(self, data: str) -> None:
        if self._in_date_label:
            self._date_label_parts.append(data)
        if self._in_availability:
            self._availability_parts.append(data)
        if self._in_price:
            self._price_parts.append(data)


def _available_count(html: str, slots: list[dict[str, object]]) -> int:
    match = _AVAILABLE_COUNT_RE.search(html)
    if match:
        return int(match.group(1))
    return sum(1 for slot in slots if slot.get("available") is True)


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get("response")
    args = context.get("args")
    if not isinstance(response, dict) or not isinstance(args, dict):
        raise ValueError("Missing processor context")

    body = response.get("body")
    if not isinstance(body, str):
        raise ValueError("Expected HTML response body")

    parser = TimeSlotsParser()
    parser.feed(body)
    parser.close()

    selected_date = args.get("date")
    if selected_date is None:
        for option in parser.date_options:
            if option.get("selected") is True:
                selected_date = option.get("date")
                break

    context["output"] = {
        "mode": "collect",
        "selected_date": selected_date,
        "date_options": parser.date_options,
        "available_count": _available_count(body, parser.slots),
        "count": len(parser.slots),
        "slots": parser.slots,
    }
    return context
