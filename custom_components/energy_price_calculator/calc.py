"""Pure price calculation helpers (no Home Assistant imports, easy to test)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

START_KEYS = ("from", "start", "start_time", "time", "datetime", "date", "begin")
END_KEYS = ("till", "to", "end", "end_time", "until")
PRICE_KEYS = ("price", "value", "total", "market_price", "marketPrice")


def parse_dt(value: Any) -> datetime | None:
    """Parse an ISO string or datetime into an aware/naive datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def supplier_price(
    market: float,
    extra_cost: float,
    tax: float,
    vat_percent: float,
    source_includes_vat: bool = False,
) -> float:
    """Return supplier price: (market + extra_cost + tax) * (1 + vat/100).

    If the source price already includes VAT it is converted to ex-VAT first.
    """
    factor = 1 + vat_percent / 100
    if source_includes_vat:
        market = market / factor
    return (market + extra_cost + tax) * factor


def normalize_prices(rows: Any) -> list[dict[str, Any]]:
    """Convert a list of price records in many formats into [{start,end,price}].

    Accepts dicts using from/start/time keys and price/value keys, and
    [time, price] pairs. End defaults to the next record's start (or +1 interval).
    """
    if not isinstance(rows, Iterable) or isinstance(rows, (str, bytes, dict)):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        start = end = price = None
        if isinstance(row, dict):
            for k in START_KEYS:
                if k in row and (start := parse_dt(row[k])) is not None:
                    break
            for k in END_KEYS:
                if k in row and (end := parse_dt(row[k])) is not None:
                    break
            for k in PRICE_KEYS:
                if k in row and row[k] is not None:
                    try:
                        price = float(row[k])
                    except (TypeError, ValueError):
                        price = None
                    break
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            start = parse_dt(row[0])
            try:
                price = float(row[1])
            except (TypeError, ValueError):
                price = None
        if start is None or price is None:
            continue
        out.append({"start": start, "end": end, "price": price})
    out.sort(key=lambda r: r["start"])
    for i, r in enumerate(out):
        if r["end"] is None:
            if i + 1 < len(out):
                r["end"] = out[i + 1]["start"]
            elif i > 0:
                r["end"] = r["start"] + (r["start"] - out[i - 1]["start"])
            else:
                r["end"] = r["start"] + timedelta(hours=1)
    return out


def apply_supplier(
    rows: list[dict[str, Any]],
    extra_cost: float,
    tax: float,
    vat_percent: float,
    source_includes_vat: bool = False,
) -> list[dict[str, Any]]:
    """Apply the supplier formula to every normalized record."""
    return [
        {
            **r,
            "price": supplier_price(
                r["price"], extra_cost, tax, vat_percent, source_includes_vat
            ),
        }
        for r in rows
    ]


def current_row(rows: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """Return the record covering *now*."""
    for r in rows:
        if r["start"] <= now < r["end"]:
            return r
    return None


def next_row(rows: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """Return the first record that starts after *now*."""
    for r in rows:
        if r["start"] > now:
            return r
    return None


def day_rows(rows: list[dict[str, Any]], day: datetime) -> list[dict[str, Any]]:
    """Records starting on the (local) calendar date of *day*."""
    d = day.date()
    return [r for r in rows if r["start"].astimezone(day.tzinfo).date() == d]


def stats(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Min / max / average (time weighted) of the given records."""
    if not rows:
        return None
    total = sum((r["end"] - r["start"]).total_seconds() for r in rows)
    if total > 0:
        avg = sum(r["price"] * (r["end"] - r["start"]).total_seconds() for r in rows) / total
    else:
        avg = sum(r["price"] for r in rows) / len(rows)
    lo = min(rows, key=lambda r: r["price"])
    hi = max(rows, key=lambda r: r["price"])
    return {"min": lo, "max": hi, "avg": avg}
