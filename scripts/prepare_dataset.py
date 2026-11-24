"""
گونجاندنی داتای ڕاستەقینە (بۆ نموونە GSMArena لە Kaggle) بۆ شێوەی PriceAI.

داتای Kaggle ناوی ستوونی جیاوازی هەیە و بەهاکانیشی وەک دەقن، بۆ نموونە
"8GB RAM" یان "6.1 inches". ئەم سکریپتە:
  1. ستوونەکان بە پێی فایلی mapping دەگۆڕێت بۆ ناوەکانی PriceAI
  2. ژمارەکان لە ناو دەقەکان دەردەهێنێت
  3. ئاستی پرۆسێسەر (chipset_tier) لە ناوی پرۆسێسەرەکەوە دیاری دەکات
  4. نرخ دەگۆڕێت بۆ دۆلار (ئەگەر پێویست بوو)
  5. data/phones.csv دەنووسێت

بەکارهێنان:
    python scripts/prepare_dataset.py raw.csv --map scripts/mapping_example.json
    python scripts/prepare_dataset.py raw.csv --map my_map.json --rate 0.012   # INR → USD

دوای ئەوە:
    python -m backend.ml.train
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.ml import features as F  # noqa: E402

NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def first_number(v):
    if pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = NUM_RE.search(str(v).replace(",", ""))
    return float(m.group(1)) if m else None


def storage_gb(v):
    """'256GB' → 256،  '1TB' → 1024"""
    if pd.isna(v):
        return None
    s = str(v).upper()
    n = first_number(s)
    if n is None:
        return None
    return n * 1024 if "TB" in s else n


def yes_no(v):
    if pd.isna(v):
        return None
    s = str(v).strip().lower()
    if s in ("1", "yes", "true", "y", "supported"):
        return 1
    if s in ("0", "no", "false", "n", "", "not supported"):
        return 0
    return 1 if ("5g" in s or "yes" in s or "nfc" in s) else 0


def display_type(v):
    if pd.isna(v):
        return None
    s = str(v).upper()
    return "OLED" if ("OLED" in s or "AMOLED" in s or "RETINA XDR" in s) else "LCD"


# ئاستی پرۆسێسەر لە کاتی دەرچوونیدا (1 = سەرەتایی … 5 = پێشەنگ).
# ڕیزبەندی گرنگە: یەکەم یاسا کە بگونجێت وەردەگیرێت.
TIER_RULES = [
    (5, r"snapdragon 8(s|\+)? (4g )?gen|snapdragon 8 elite|snapdragon 8[3-9]\d|sm8[4-9]\d\d|"
        r"dimensity 9\d{3}|apple a(1[5-9]|[2-9]\d)|tensor|exynos (2\d{3}|98[12]\d|99\d)(?!\d)|"
        r"kirin (9\d{3}|9[89]\d)|xring"),
    (4, r"snapdragon 7\+? gen|snapdragon 7s gen [3-9]|snapdragon 7[6-9]\d|snapdragon 8[0-2]\d|"
        r"dimensity 8\d{3}|dimensity 1[1-3]\d\d|dimensity 1000|apple a1[2-4]|exynos (1[3-9]\d\d|980)\b|"
        r"kirin (8\d{3}|97\d)"),
    (3, r"snapdragon 7s gen [12]|snapdragon 6 gen|snapdragon 6s gen [3-9]|snapdragon 7[0-5]\d|"
        r"snapdragon 69\d|dimensity 7\d{3}|dimensity (8|9|10[5-9])\d\d?\b|helio g(99|100)|\bg100\b|"
        r"exynos 1[0-2]\d\d|kirin 8[1-2]\d|unisoc t8\d\d|qcm6490|apple a\d"),
    (2, r"snapdragon 6s? (4g )?gen|snapdragon 4\+? gen|snapdragon 4s gen|snapdragon 6[0-8]\d|"
        r"dimensity 6\d{3}|dimensity 7\d\d\b|helio g[5-9]\d|helio p[6-9]\d|exynos (9[56]\d\d|9 octa|8\d{2,3})|"
        r"unisoc t[67]\d\d|tiger|\bt6\d\d?\b|kirin 7\d\d|mt87[68]\d|mt878|qcm4490"),
    (1, r"helio|unisoc|spreadtrum|\bsc\d{4}|snapdragon [1-5]\d\d|\bqm215|\bmt\s?6\d{3}|\bmtk|\bmt\d{3,4}|"
        r"mediatek (a\d\d|6\d{3})|kirin|exynos (7\d{3}|850)|cortex|jlq|quad[- ]core|hello a"),
]

# هەڵەی ڕێنووسی باو لە داتای ڕاستەقینەدا
_TYPOS = {"snpdragon": "snapdragon", "qualcmm": "qualcomm", "qualcom ": "qualcomm ", "hellio": "helio ",
          "hislicon": "hisilicon", "hisilion": "hisilicon", "unisc": "unisoc", "unison": "unisoc",
          "meditek": "mediatek", "meiatek": "mediatek", "mediatak": "mediatek", "speadtrum": "spreadtrum",
          "cortx": "cortex", "cort x": "cortex"}


def chipset_tier(name):
    if pd.isna(name):
        return None
    s = str(name).lower()
    for wrong, right in _TYPOS.items():
        s = s.replace(wrong, right)
    s = re.sub(r"\s+", " ", s)
    for tier, pattern in TIER_RULES:
        if re.search(pattern, s):
            return tier
    return None  # Imputer لە کاتی ڕاهێناندا پڕی دەکاتەوە


CONVERTERS = {
    "number": first_number, "storage": storage_gb, "yesno": yes_no,
    "display": display_type, "text": lambda v: None if pd.isna(v) else str(v).strip(),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="فایلی CSV ی ڕەسەن")
    ap.add_argument("--map", required=True, help="فایلی JSON ی گونجاندن")
    ap.add_argument("--rate", type=float, default=1.0, help="ڕێژەی گۆڕینی نرخ بۆ دۆلار")
    ap.add_argument("--out", default=str(ROOT / "data" / "phones.csv"))
    args = ap.parse_args()

    raw = pd.read_csv(args.raw)
    mapping = json.loads(Path(args.map).read_text(encoding="utf-8"))
    out = pd.DataFrame()
    for target, spec in mapping["columns"].items():
        src, conv = spec["from"], spec.get("as", "number")
        if src not in raw.columns:
            print(f"⚠️  ستوونی '{src}' لە فایلەکەدا نییە (بۆ {target})")
            out[target] = None
            continue
        out[target] = raw[src].map(CONVERTERS[conv])

    if "chipset_tier" not in out and "chipset" in out:
        out["chipset_tier"] = out["chipset"].map(chipset_tier)
    if "os" not in out and "brand" in out:
        out["os"] = out["brand"].map(lambda b: "iOS" if str(b).lower() == "apple" else "Android")
    out["price_usd"] = pd.to_numeric(out["price_usd"], errors="coerce") * args.rate

    missing = [c for c in F.ALL + [F.TARGET] if c not in out]
    for c in missing:
        print(f"⚠️  '{c}' نییە، بە بەتاڵی دادەنرێت (Imputer پڕی دەکاتەوە)")
        out[c] = None

    out = out[out["price_usd"] > 0]
    cols = ["brand", "model", "chipset"] + [c for c in F.ALL if c != "brand"] + [F.TARGET]
    out = out[[c for c in cols if c in out]]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"✓ {len(out)} ڕیز نووسرا بۆ {args.out}")
    print(out.isna().mean().round(3).rename("ڕێژەی بەتاڵ").to_string())


if __name__ == "__main__":
    main()
