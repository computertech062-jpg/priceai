"""
تاقیکردنەوەی مێژووی نرخ و پێشبینیی نرخ بە پێی کات.
داتای دروستکراو بەکاردێت (نەک data/price_history.csv) بۆ ئەوەی ئەنجامەکە زانراو بێت.
ڕاکردن:  python -m pytest -q
"""
import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.ml.forecast import Forecaster, apple_battery, parse_date, segment
from backend.ml.history import PriceHistory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_price_history import fx, parse_page, pick_snapshots, release_date  # noqa: E402

YEARLY_DROP = 0.10  # هەموو مۆبایلە دروستکراوەکان ساڵانە 10% دادەبەزن


def make_history(tmp_path, n_phones=8):
    rows, raw = [], []
    for i in range(n_phones):
        rel = date(2018 + i % 6, 9, 20)
        model = f"Testco Phone {i}"
        for age in range(0, 49, 6):
            d = date(rel.year + (rel.month + age - 1) // 12, (rel.month + age - 1) % 12 + 1, 20)
            price = 500 * (1 + i / 10) * (1 - YEARLY_DROP) ** (age / 12)
            rows.append({"brand": "Testco", "model": model, "chipset_tier": 4, "release_date": rel.isoformat(),
                         "snapshot": d.strftime("%Y%m%d000000"), "date": d.isoformat(), "age_months": age,
                         "bdt_per_usd": 100.0, "price_type": "unofficial", "ram_gb": 8.0, "storage_gb": 128.0,
                         "price_bdt": price * 100, "price_usd": round(price, 2)})
        raw.append({"Name": model, "Released": f"{rel.year}, September 20", "General_Updated": f"March 1, {rel.year + 1}"})
    raw.append({"Name": "Testco New", "Released": "2025, September 20", "General_Updated": "March 20, 2026"})
    hp, rp = tmp_path / "price_history.csv", tmp_path / "raw.csv"
    pd.DataFrame(rows).to_csv(hp, index=False)
    pd.DataFrame(raw).to_csv(rp, index=False)
    return hp, rp


@pytest.fixture()
def forecaster(tmp_path):
    hp, rp = make_history(tmp_path)
    return Forecaster(hp, rp, today=date(2026, 9, 20))


def test_forecast_recovers_known_depreciation(forecaster):
    r = forecaster.forecast("Testco New", "Testco", 4, 1000)
    assert r["available"]
    assert r["observed"] == {"price": 1000, "date": "2026-03-20", "age_months": 6}
    assert r["today"]["age_months"] == 12 and r["next_year"]["age_months"] == 24
    # 6 مانگ: 1000 × 0.9^0.5 ،  پاشان ساڵێکی تر: × 0.9
    assert r["today"]["price"] == pytest.approx(1000 * 0.9 ** 0.5, abs=2)
    assert r["next_year"]["price"] == pytest.approx(1000 * 0.9 ** 1.5, abs=2)
    assert r["change_pct"] == pytest.approx(-10.0, abs=0.3)
    assert r["next_year"]["low"] <= r["next_year"]["price"] <= r["next_year"]["high"]
    assert r["scope"] == "brand_segment" and "battery" not in r


def test_forecast_unknown_phone(forecaster):
    assert forecaster.forecast("Nope", "Testco", 4, 500)["available"] is False


def test_backtest_no_future_leakage(forecaster):
    bt = forecaster.backtest()
    assert bt["available"] and bt["n"] > 0
    assert bt["mape"] < 1.0  # داتای دروستکراو: هەمان ڕێژە، هەڵە نزیکەی سفر
    assert bt["naive_mape"] > 5
    # یەکەم مۆبایل (2018) هیچ مۆبایلێکی پێش خۆی نییە، بۆیە ناکەوێتە Backtest
    assert "Testco Phone 0" not in {e["model"] for e in bt["examples"]}


def test_history_series(tmp_path):
    hp, _ = make_history(tmp_path, n_phones=2)
    h = PriceHistory(hp)
    s = h.series("Testco Phone 1", 8.0, 128.0)
    assert s["available"] and s["exact_variant"] and s["price_type"] == "unofficial"
    assert s["summary"]["yearly_pct"] == pytest.approx(-10.0, abs=0.3)
    assert h.series("Nope")["available"] is False
    assert PriceHistory(tmp_path / "missing.csv").available is False


def test_segments_and_battery():
    assert segment("Apple", "Apple iPhone 17 Pro", 5) == "apple-pro"
    assert segment("Apple", "Apple iPhone XS Max", 5) == "apple-pro"
    assert segment("Apple", "Apple iPhone 17", 5) == "apple-base"
    assert segment("Apple", "Apple iPhone SE (2022)", 4) == "apple-budget"
    assert segment("Apple", "Apple iPhone 16e", 5) == "apple-budget"
    assert segment("Samsung", "Galaxy S24", 5) == "flagship"
    assert segment("Samsung", "Galaxy A15", 2) == "budget"
    assert apple_battery("Apple iPhone 17", 12)["health_pct"] == 93   # 1000 سووڕ
    assert apple_battery("Apple iPhone 13", 12)["health_pct"] == 85   # 500 سووڕ


def test_date_parsing():
    assert parse_date("2025, September 19") == date(2025, 9, 19)
    assert parse_date("2025, October") == date(2025, 10, 15)
    assert parse_date("August 5, 2026") == date(2026, 8, 5)
    assert parse_date("February 30, 2024") == date(2024, 2, 15)
    assert parse_date("Coming soon") is None
    assert release_date("2021, September 24") == date(2021, 9, 24)


def test_parse_page_old_and_new_layouts():
    old = """<h1>Apple iPhone 13</h1><p>৳118,999.00</p><p>৳114,999.00</p><span>You Save:</span>
      <b>Variant:</b><b>Official</b><p>(128GB) ৳1,14,999</p><b>Unofficial</b>
      <p>(128GB) ৳91,000</p><p>(128GB) USA ৳86,000</p><p>(256GB) USA ৳1,00,000</p><b>Brand:</b>"""
    r = parse_page(old, default_ram=4.0)
    assert r["official"] == {(4.0, 128.0): 114999.0}
    # نرخی بێ نیشانە (دوکانی ناوخۆ) لە پێش «USA» ە: iPhone ی ئەمریکی eSIM ـە و بەرهەمێکی ترە
    assert r["unofficial"] == {(4.0, 128.0): 91000.0, (4.0, 256.0): 100000.0}
    assert r["list"] == 114999.0
    new = """<h1>Samsung Galaxy A54</h1><p>৳53,999.00</p><b>Brand:</b><div>…</div>
      <b>Official</b><p>Official prices and mobile phones are available only in authorized shops.</p>
      <p>8GB 128GB  ৳ 61,199</p><b>Unofficial</b><p>Unofficial prices…</p>
      <p>8GB+128GB ৳ 36,000 / 8GB 256GB ৳ 40,000</p><b>Global price</b>"""
    r = parse_page(new)
    assert r["official"] == {(8.0, 128.0): 61199.0}
    assert r["unofficial"] == {(8.0, 128.0): 36000.0, (8.0, 256.0): 40000.0}


def test_snapshot_selection_and_fx():
    stamps = [f"2021{m:02d}01000000" for m in range(1, 13)]
    picked = pick_snapshots(stamps, date(2021, 3, 15), max_n=4)
    assert picked[0] == "20210401000000" and picked[-1] == "20211201000000" and len(picked) == 4
    assert fx("2023-07") == 108.8 and fx("2021-03") == 84.8 and fx("2030-01") == 122.0
    assert math.isclose(fx("2015-01"), 83.9)
