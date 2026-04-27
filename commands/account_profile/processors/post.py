"""Output shaping for account profile."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re


_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", unescape(value)).strip()
    return cleaned or None


def _strip_tags(value: str) -> str | None:
    parser = TextExtractor()
    parser.feed(value)
    parser.close()
    return parser.text()


def _section(html: str, class_name: str) -> str | None:
    start = html.find(class_name)
    if start < 0:
        return None
    div_start = html.rfind("<div", 0, start)
    if div_start < 0:
        return None
    depth = 0
    for match in re.finditer(r"</?div\b[^>]*>", html[div_start:], re.I):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[div_start : div_start + match.end()]
        else:
            depth += 1
    return None


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str | None:
        return _clean_text(" ".join(self.parts))


def _extract_profile_fields(html: str) -> dict[str, str | None]:
    match = re.search(r'<section class="customer-profile-details".*?<dl>(.*?)</dl>', html, re.S)
    if not match:
        return {"name": None, "surname": None, "phone": None, "email": None}
    fields: dict[str, str | None] = {}
    for item in re.finditer(r"<dt>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", match.group(1), re.S):
        label = (_strip_tags(item.group(1)) or "").strip().lower().replace(" ", "_")
        value = _strip_tags(item.group(2))
        if label:
            fields[label] = value
    return {
        "name": fields.get("name"),
        "surname": fields.get("surname"),
        "phone": fields.get("phone"),
        "email": fields.get("email"),
    }


def _extract_rimi_money(html: str) -> dict[str, object] | None:
    section = _section(html, "my-profile__balance")
    if not section:
        return None
    amount = _first_text(section, r'<div class="main">(.*?)</div>')
    if amount is None:
        return None
    return {"balance": amount, "currency": "EUR"}


def _first_text(html: str, pattern: str) -> str | None:
    match = re.search(pattern, html, re.S)
    return _strip_tags(match.group(1)) if match else None


def _extract_payment_cards(html: str) -> list[dict[str, object]]:
    section = _section(html, "my-profile__methods")
    if not section:
        return []
    ids = re.findall(r'name="paymentCardId"\s+value="([^"]+)"', section)
    pans = [_strip_tags(match.group(1)) for match in re.finditer(r'<div class="list__card">.*?<span>(.*?)</span>', section, re.S)]
    cards: list[dict[str, object]] = []
    for index, pan in enumerate(pans):
        cards.append({"id": ids[index] if index < len(ids) else None, "pan_number": pan})
    return cards


def _extract_favorite_store(html: str) -> dict[str, object] | None:
    section = _section(html, "my-profile__favourite")
    if not section:
        return None
    name = _first_text(section, r'<div class="list__favourite">\s*<span>(.*?)</span>')
    if name is None:
        return None
    notes = [_strip_tags(match.group(1)) for match in re.finditer(r'<span class="notes">(.*?)</span>', section, re.S)]
    return {"name": name, "address": notes[0] if notes else None}


def _extract_addresses(html: str) -> list[dict[str, object]]:
    section = _section(html, "my-profile__address")
    if not section:
        return []
    ids = re.findall(r'name="addressId"\s+value="([^"]+)"', section)
    addresses = [_strip_tags(match.group(1)) for match in re.finditer(r'<div class="list__address"[^>]*>\s*<span>(.*?)</span>', section, re.S)]
    notes = [_strip_tags(match.group(1)) for match in re.finditer(r'<span class="notes">(.*?)</span>', section, re.S)]
    result: list[dict[str, object]] = []
    for index, address in enumerate(addresses):
        result.append(
            {
                "id": ids[index] if index < len(ids) else None,
                "address": address,
                "notes": notes[index] if index < len(notes) else None,
            }
        )
    return result


def _extract_car_plates(html: str) -> list[dict[str, object]]:
    section = _section(html, "my-profile__plates")
    if not section:
        return []
    ids = re.findall(r'name="carPlateId"\s+value="([^"]+)"', section)
    plates = [_strip_tags(match.group(1)) for match in re.finditer(r'<p class="list__plate"[^>]*>(.*?)</p>', section, re.S)]
    return [{"id": ids[index] if index < len(ids) else None, "plate": plate} for index, plate in enumerate(plates)]


def run(context: dict[str, object]) -> dict[str, object]:
    response = context.get("response")
    if not isinstance(response, dict):
        raise ValueError("Missing response context")

    body = response.get("body")
    if not isinstance(body, str):
        raise ValueError("Expected HTML response body")

    profile = _extract_profile_fields(body)
    context["output"] = {
        "signed_in": any(profile.values()),
        "profile": profile,
        "rimi_money": _extract_rimi_money(body),
        "payment_cards": _extract_payment_cards(body),
        "favorite_store": _extract_favorite_store(body),
        "addresses": _extract_addresses(body),
        "car_plates": _extract_car_plates(body),
    }
    return context
