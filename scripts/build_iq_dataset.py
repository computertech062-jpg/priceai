"""
دروستکردنی data/phones.csv لە دوو فایل: تایبەتمەندی + نرخی بازاڕی کوردستان/عێراق.

بۆچی دوو فایل؟
  - تایبەتمەندییەکان (specs.csv) ناگۆڕێن: هەر مۆدێلێک یەک ڕیز.
  - نرخەکان (prices_iq.csv) هەموو مانگێک دەگۆڕێن: هەر جۆرێک (RAM + بیرگە) یەک ڕیز،
    لەگەڵ سەرچاوە و بەروار. بەم شێوەیە تەنها فایلی نرخ نوێ دەکەیتەوە.

specs.csv:
    brand,model,chipset,release_year,main_camera_mp,front_camera_mp,battery_mah,fast_charge_w,
    screen_inch,refresh_rate_hz,display_type,weight_g,os,has_5g,has_nfc

prices_iq.csv:
    brand,model,ram_gb,storage_gb,price,currency,source,date
    - currency: USD یان IQD
    - source: ناوی دوکان یان ماڵپەڕ (بۆ نموونە ناوی دوکانێک لە هەولێر، یان ماڵپەڕێکی فرۆشتن)
    - date: YYYY-MM-DD
    - ئەگەر یەک جۆر چەند نرخی هەبوو (چەند دوکان)، میدیان (Median) وەردەگیرێت.

بەکارهێنان:
    python scripts/build_iq_dataset.py --specs data/specs.csv --prices data/prices_iq.csv --iqd-rate 1450

دوای ئەوە:
    python -m backend.ml.train
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from backend.ml import features as F  # noqa: E402
from prepare_dataset import chipset_tier  # noqa: E402

KEY = ["brand", "model"]
SPEC_COLS = ["brand", "model", "chipset", "release_year", "main_camera_mp", "front_camera_mp",
             "battery_mah", "fast_charge_w", "screen_inch", "refresh_rate_hz", "display_type",
             "weight_g", "os", "has_5g", "has_nfc"]
PRICE_COLS = ["brand", "model", "ram_gb", "storage_gb", "price", "currency", "source", "date"]
MIN_ROWS = 200


def norm_key(df):
    for c in KEY:
        df[c] = df[c].astype(str).str.strip()
    df["_k"] = (df["brand"] + "|" + df["model"]).str.lower().str.replace(r"\s+", " ", regex=True)
    return df


def read(path, cols, name):
    df = pd.read_csv(path, encoding="utf-8-sig")  # utf-8-sig: بۆ فایلی Excel
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        sys.exit(f"✗ ئەم ستوونانە لە {name} دا نین: {missing}")
    return norm_key(df.dropna(subset=KEY))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default=str(ROOT / "data" / "specs.csv"))
    ap.add_argument("--prices", default=str(ROOT / "data" / "prices_iq.csv"))
    ap.add_argument("--iqd-rate", type=float, default=None,
                    help="چەند دینار = 1 دۆلار (نرخی بازاڕ، بۆ نموونە 1450). پێویستە ئەگەر نرخی IQD هەبێت")
    ap.add_argument("--out", default=str(ROOT / "data" / "phones.csv"))
    args = ap.parse_args()

    specs = read(args.specs, SPEC_COLS, "specs")
    prices = read(args.prices, PRICE_COLS, "prices")
    problems = 0

    # --- پشکنینی تایبەتمەندییەکان ---
    dup = specs[specs.duplicated("_k", keep=False)]
    if len(dup):
        problems += 1
        print(f"⚠️  مۆدێلی دووبارە لە specs (یەکەمیان وەردەگیرێت): {sorted(set(dup['model']))}")
        specs = specs.drop_duplicates("_k")
    empty = specs[SPEC_COLS].isna().sum()
    empty = empty[empty > 0]
    if len(empty):
        print("ℹ️  خانەی بەتاڵ لە specs (Imputer پڕیان دەکاتەوە، بەڵام باشترە پڕیان بکەیتەوە):")
        print("    " + empty.to_string().replace("\n", "\n    "))

    # --- نرخ: گۆڕین بۆ دۆلار ---
    prices["currency"] = prices["currency"].fillna("USD").astype(str).str.upper().str.strip()
    prices["price"] = pd.to_numeric(prices["price"].astype(str).str.replace(",", ""), errors="coerce").astype(float)
    bad_cur = prices[~prices["currency"].isin(["USD", "IQD"])]
    if len(bad_cur):
        sys.exit(f"✗ دراوی نەناسراو (تەنها USD یان IQD): {sorted(set(bad_cur['currency']))}")
    if (prices["currency"] == "IQD").any():
        if not args.iqd_rate:
            sys.exit("✗ نرخی IQD هەیە. --iqd-rate بنووسە (بۆ نموونە --iqd-rate 1450)")
        iqd = prices["currency"] == "IQD"
        prices.loc[iqd, "price"] = prices.loc[iqd, "price"] / args.iqd_rate
    prices = prices[prices["price"] > 0]

    # نرخی نائاسایی: زۆر جیاواز لە میدیانی هەمان جۆر
    grp = prices.groupby(["_k", "ram_gb", "storage_gb"])["price"]
    ratio = prices["price"] / grp.transform("median")
    odd = prices[(ratio > 1.4) | (ratio < 0.6)]
    if len(odd):
        problems += 1
        print("⚠️  نرخی نائاسایی (زیاتر لە 40% جیاواز لە دوکانەکانی تر). پشکنینیان بکە:")
        print("    " + odd[["brand", "model", "ram_gb", "storage_gb", "price", "source"]].to_string(index=False)
              .replace("\n", "\n    "))

    agg = (prices.groupby(["_k", "ram_gb", "storage_gb"], as_index=False)
           .agg(price_usd=("price", "median"), n_sources=("price", "size"),
                source=("source", lambda s: " · ".join(sorted(set(s.dropna().astype(str))))),
                price_date=("date", "max")))
    agg["price_usd"] = agg["price_usd"].round()

    # --- لکاندنی نرخ بە تایبەتمەندی ---
    no_specs = sorted(set(agg["_k"]) - set(specs["_k"]))
    if no_specs:
        problems += 1
        print(f"⚠️  نرخیان هەیە بەڵام تایبەتمەندییان نییە (ناوەکە وەک specs بنووسە): {no_specs}")
    no_price = sorted(set(specs["_k"]) - set(agg["_k"]))
    if no_price:
        print(f"ℹ️  تایبەتمەندییان هەیە بەڵام نرخیان نییە (بەکارنایەن): {no_price}")

    out = agg.merge(specs, on="_k", how="inner")
    out["chipset_tier"] = out["chipset"].map(chipset_tier)
    unknown_chip = sorted(set(out.loc[out["chipset_tier"].isna(), "chipset"].dropna()))
    if unknown_chip:
        problems += 1
        print(f"⚠️  ئاستی ئەم پرۆسێسەرانە نەناسرایەوە (لە TIER_RULES ی prepare_dataset.py زیادیان بکە): {unknown_chip}")

    cols = ["brand", "model", "chipset"] + [c for c in F.ALL if c != "brand"] + \
           [F.TARGET, "n_sources", "source", "price_date"]
    out = out[cols].sort_values(["brand", "model", "ram_gb", "storage_gb"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    print(f"\n✓ {len(out)} ڕیز ({out['model'].nunique()} مۆدێل) نووسرا بۆ {args.out}")
    if args.iqd_rate:
        print(f"  ڕێژەی گۆڕین: 1 USD = {args.iqd_rate:g} IQD")
    if len(out) < MIN_ROWS:
        print(f"⚠️  تەنها {len(out)} ڕیز. بۆ مۆدێلێکی باش لانیکەم {MIN_ROWS} ڕیز پێویستە.")
    print("پاشان:  python -m backend.ml.train" + ("" if not problems else "   (سەرەتا ئاگادارییەکان چاک بکە)"))


if __name__ == "__main__":
    main()
