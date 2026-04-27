"""Request preparation for checkout time slots."""

from __future__ import annotations

import re


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def run(context: dict[str, object]) -> dict[str, object]:
    args = context.get("args")
    request = context.get("request")
    if not isinstance(args, dict) or not isinstance(request, dict):
        raise ValueError("Missing processor context")

    date = args.get("date")
    query = request.setdefault("query", {})
    headers = request.setdefault("headers", {})
    if not isinstance(query, dict) or not isinstance(headers, dict):
        raise ValueError("Expected request query and headers to be objects")

    headers["referer"] = "https://www.rimi.ee/epood/en/checkout"

    if date is None:
        headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        return context

    if not isinstance(date, str) or not _DATE_RE.fullmatch(date):
        raise ValueError("Expected --date in YYYY-MM-DD format")

    path = "/epood/en/checkout/delivery/collect/edit/time-slots"
    request["path_template"] = path
    request["url_template"] = f"https://www.rimi.ee{path}"
    request["path"] = path
    request["url"] = f"https://www.rimi.ee{path}"
    query["date"] = date
    headers["accept"] = "*/*"
    headers["referer"] = "https://www.rimi.ee/epood/en/checkout/delivery/collect/time-slots"
    return context
