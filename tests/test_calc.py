import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components" / "energy_price_calculator"))
import calc  # noqa: E402

TZ = timezone(timedelta(hours=1))


def test_formula_matches_entsoe_template():
    # ((p + 0.021 + 0.092) * 1.21)
    assert abs(calc.supplier_price(0.17827, 0.021, 0.092, 21) - (0.17827 + 0.113) * 1.21) < 1e-9


def test_source_includes_vat():
    p = calc.supplier_price(0.121, 0.0, 0.0, 21, source_includes_vat=True)
    assert abs(p - 0.121) < 1e-9


def test_normalize_frank_format_and_current():
    rows = [
        {"from": "2026-11-21T00:00:00+01:00", "till": "2026-11-21T01:00:00+01:00", "price": 0.187},
        {"from": "2026-11-21T01:00:00+01:00", "till": "2026-11-21T02:00:00+01:00", "price": 0.2},
    ]
    n = calc.normalize_prices(rows)
    now = datetime(2026, 11, 21, 1, 30, tzinfo=TZ)
    assert calc.current_row(n, now)["price"] == 0.2
    assert calc.next_row(n, datetime(2026, 11, 21, 0, 30, tzinfo=TZ))["price"] == 0.2
    s = calc.stats(calc.day_rows(n, now))
    assert abs(s["avg"] - 0.1935) < 1e-9


def test_normalize_time_price_and_pairs_without_end():
    n = calc.normalize_prices([
        {"time": "2026-11-21T00:00:00+01:00", "price": "0.1"},
        ["2026-11-21T01:00:00+01:00", 0.3],
    ])
    assert len(n) == 2 and n[0]["end"] == n[1]["start"]
    assert n[1]["end"] - n[1]["start"] == timedelta(hours=1)


def test_garbage():
    assert calc.normalize_prices(None) == []
    assert calc.normalize_prices([{"x": 1}, "abc"]) == []
