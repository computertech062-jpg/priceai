"""
گۆڕینی داتای Kaggle «Global Mobile Phone Specifications and Prices 2026» بۆ data/phones.csv

ئاگاداری: ئەم داتایە لە mobiledokan.co (بەنگلادیش) کۆکراوەتەوە و نرخەکانی بە تاکای
بەنگلادیشین (৳ BDT)، نەک نرخی جیهانی. ئەم سکریپتە دەیانگۆڕێت بۆ دۆلار بە --rate.

نرخی هەر جۆرێک (RAM + بیرگە) بەم ڕیزبەندییە وەردەگیرێت:
  1. Prices_Unofficial (بازاڕی ناڕەسمی، نزیکترە لە بازاڕی عێراق کە کاڵاکان لە دوبەیەوە دێن)
     ئەگەر نرخی چەند وڵاتێک هەبوو (USA/UAE/...)، UAE وەردەگیرێت، ئەگەرنا میدیان.
  2. Prices_Official
  3. ستوونی Price (نرخی بنەڕەت، بۆ کەمترین RAM و بیرگە). 94% ی کات هەمان نرخی ڕەسمییە.

ڕێکخستنی نرخی ڕەسمی: نرخی ڕەسمیی بەنگلادیش باج و گومرگی زۆری تێدایە
(نزیکەی 1.3× ی نرخی ناڕەسمی). بۆ ئەوەی هەموو نرخەکان لە یەک ئاستدا بن، نرخی ڕەسمی
دابەش دەکرێت بەسەر ڕێژەی هەمان براند (لە خودی داتاکەوە دەژمێردرێت). براندێک کە لە
بەنگلادیش فرۆشتنی ڕەسمیی نییە، نرخەکەی وەک خۆی دەمێنێتەوە. بە --no-adjust ناچالاک دەبێت.

بەکارهێنان:
    python scripts/convert_mobiledokan.py
    python scripts/convert_mobiledokan.py --rate 122 --min-year 2019 --prefer official
دوای ئەوە:
    python -m backend.ml.train
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from backend.ml import features as F  # noqa: E402
from prepare_dataset import chipset_tier  # noqa: E402

RAW = ROOT / "data" / "Global_Mobile_Phone_Specifications_and_Prices_2026.csv"
NUM = r"(\d+(?:\.\d+)?)"
# "8GB 256GB ৳39,990" ،  "12GB 1TB ৳1,40,000" ،  "256GB ৳1,99,999" (Apple) ،  "256GB UAE ৳1,07,000"
VARIANT_RE = re.compile(r"(?:(\d+(?:\.\d+)?)\s*GB\s+)?(\d+(?:\.\d+)?)\s*(GB|TB)(?:\s+([A-Z]{2,4}))?\s*৳\s*([\d,]+)")
TAKA_RE = re.compile(r"৳\s*([\d,]+)")


def num(v, pattern=NUM):
    if pd.isna(v):
        return None
    m = re.search(pattern, str(v).replace(",", ""), re.I)
    return float(m.group(1)) if m else None


def taka(s):
    return float(s.replace(",", ""))


# قەبارە ستانداردەکان. هەر بەهایەکی تر هەڵەی ڕێنووسە لە سەرچاوەکەدا (بۆ نموونە "28GB" لە جیاتی "128GB")
STANDARD_STORAGE = {16, 32, 64, 128, 256, 512, 1024, 2048}
STANDARD_RAM = {1, 1.5, 2, 3, 4, 6, 8, 10, 12, 16, 18, 20, 24}


def parse_variants(text, default_ram=None):
    """'6GB 128GB ৳14,999 / 8GB 256GB ৳16,499' → [(6,128,14999), (8,256,16499)]
    ئەگەر RAM نەنووسرابوو (Apple)، default_ram بەکاردێت."""
    if pd.isna(text):
        return []
    found = {}
    for ram, sto, unit, tag, price in VARIANT_RE.findall(str(text)):
        ram = float(ram) if ram else default_ram
        if not ram:
            continue
        sto = float(sto) * (1024 if unit.upper() == "TB" else 1)
        if sto not in STANDARD_STORAGE or ram not in STANDARD_RAM:
            continue
        found.setdefault((ram, sto), []).append((tag, taka(price)))
    out = []
    for (ram, sto), prices in found.items():
        uae = [p for tag, p in prices if tag == "UAE"]
        out.append((ram, sto, uae[0] if uae else float(pd.Series([p for _, p in prices]).median())))
    return out


def min_size(text, unit="GB"):
    """'8/12 GB' → 8 ،  '128/256 GB / 1 TB' → 128 ،  '512 MB RAM' → 0.5"""
    if pd.isna(text):
        return None
    s = str(text).upper()
    m = re.search(r"(\d+(?:\.\d+)?)(?:\s*/\s*\d+(?:\.\d+)?)*\s*(TB|GB|MB)", s)
    if not m:
        return None
    v = float(m.group(1))
    return v * 1024 if m.group(2) == "TB" else v / 1024 if m.group(2) == "MB" else v


def all_sizes(text, first_only=False):
    """'64/128/256 GB' → [64,128,256] ،  '256/512 GB / 1/2TB' → [256,512,1024,2048]"""
    if pd.isna(text):
        return []
    out = []
    for nums, unit in re.findall(r"(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)*)\s*(TB|GB|MB)", str(text).upper()):
        mult = 1024 if unit == "TB" else 1 / 1024 if unit == "MB" else 1
        out += [float(n) * mult for n in re.split(r"\s*/\s*", nums)]
        if first_only:
            break
    return out


PAIR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*GB\s+(\d+(?:\.\d+)?)\s*(GB|TB)", re.I)


def configs(r, vs):
    """
    ئەو جۆرانەی (RAM + بیرگە) ئەم مۆبایلە بەڕاستی پێیان دێت.

    دەگەڕێنێتەوە: (پشتڕاستکراوە، خەمڵێنراو) — هەردووکیان وەک "8x128|8x256".
      پشتڕاستکراوە: لە Memory_Variant (لیستی فەرمیی جۆرەکان)، لە نرخی دوکانەکان، یان کاتێک
                    RAM یان بیرگە تەنها یەک بەهای هەیە (هیچ گومانێک نییە).
      خەمڵێنراو:   کاتێک تەنها لیستی RAM و لیستی بیرگە هەیە (بۆ نموونە "8/12 GB" و "128/256 GB")
                    بەبێ ئەوەی بزانین کامیان پێکەوەن. یاسا: زۆرترین RAM لەگەڵ کەمترین بیرگە نایەت.
                    (لەسەر 1066 مۆبایلی پشتڕاستکراو تاقیکرایەوە: 93% ی جۆرە ڕاستەقینەکان دەگرێت.)
    """
    lim = {k: (F.by_name(k)["min"], F.by_name(k)["max"]) for k in ("ram_gb", "storage_gb")}
    ok = lambda ram, sto: (lim["ram_gb"][0] <= ram <= lim["ram_gb"][1] and lim["storage_gb"][0] <= sto <= lim["storage_gb"][1]
                           and ram in STANDARD_RAM and sto in STANDARD_STORAGE)

    listed = {(float(a), float(b) * (1024 if u.upper() == "TB" else 1))
              for a, b, u in PAIR_RE.findall(str(r.get("Memory_Variant") or ""))}
    rams = sorted({x for x in all_sizes(r.get("Memory_RAM"), first_only=True)
                   if lim["ram_gb"][0] <= x <= lim["ram_gb"][1] and x in STANDARD_RAM})
    # نرخی دوکان بەبێ RAM (Apple: "256GB ৳...") تەنها کاتێک کە مۆبایلەکە یەک RAM ی هەیە
    one_ram = rams[0] if len(rams) == 1 else None
    shops = {(ram, sto) for col in ("Prices_Official", "Prices_Unofficial")
             for ram, sto, _ in parse_variants(r.get(col), one_ram) if ram}
    priced = {(ram, sto) for ram, sto, _ in vs}
    stos = sorted({x for x in all_sizes(r.get("Memory_Internal"))
                   if lim["storage_gb"][0] <= x <= lim["storage_gb"][1] and x in STANDARD_STORAGE})

    verified = {c for c in listed | shops | priced if ok(*c)}
    guess = set()
    # سەرچاوەکە هەندێک جار جۆرێکی بچووکتری نووسیوە کە بوونی نییە (بۆ نموونە iPhone 17 Pro ی 128GB).
    # ئەگەر دوکانەکان لانیکەم دوو جۆریان دەفرۆشن و هیچیان ئەو جۆرە بچووکەیان نییە، پشتڕاست نییە (≈).
    sold = shops | priced
    if len(shops) >= 2:
        floor = min(s for _, s in shops)
        doubtful = {c for c in verified if c[1] < floor and c not in sold}
        verified -= doubtful
        guess |= doubtful
    if not listed and rams and stos:
        if len(rams) == 1 or len(stos) == 1:  # بێ گومان: هەموو پێکهاتەکان ڕاستن
            verified |= {(a, b) for a in rams for b in stos}
        else:
            guess = {(a, b) for a in rams for b in stos
                     if not (a == rams[-1] and b == stos[0])} - verified
    fmt = lambda cs: "|".join(f"{a:g}x{b:g}" for a, b in sorted(cs))
    return fmt(verified), fmt(guess)


def base_price(text):
    """ستوونی Price: ئەگەر دوو نرخ هەبوو (کۆن ← نوێ)، دواییان نرخی ئێستایە."""
    found = TAKA_RE.findall(str(text))
    return taka(found[-1]) if found else None


def first_mp(row, cols):
    for c in cols:
        v = num(row.get(c), r"(\d+(?:\.\d+)?)\s*MP")
        if v:
            return v
    return None


# سنووری RAM و بیرگە وەک features.py (ئەگەرنا Backend ڕەتیان دەکاتەوە)
LIM = {k: (F.by_name(k)["min"], F.by_name(k)["max"]) for k in ("ram_gb", "storage_gb")}

MAIN_CAM = ["Main camera_Single", "Main camera_Dual", "Main camera_Triple", "Main camera_Quad",
            "Main camera_Penta", "Camera"]
SELFIE_CAM = ["Selfie camera_Single", "Selfie camera_Dual", "Selfie camera_Triple"]


def specs(r):
    chipset = r.get("Platform_Chipset")
    chipset = re.sub(r"\s*\(.*?\)", "", str(chipset)).strip() if pd.notna(chipset) else ""
    disp = " ".join(str(r.get(c, "")) for c in ("Display_Type", "Display_Features"))
    charge = num(r.get("Battery_Charging"), r"(\d+(?:\.\d+)?)\s*W") or num(r.get("Battery"), r"(\d+)\s*W\b")
    year = num(r.get("Released"), r"(20\d\d)") or num(r.get("Launch_Announced"), r"(20\d\d)")
    os_ = str(r.get("Platform_OS") or r.get("OS") or "")
    return {
        "brand": str(r["General_Brand"]).strip(),
        "model": str(r["Name"]).strip(),
        "chipset": chipset,
        "release_year": year,
        "chipset_tier": chipset_tier(chipset) if chipset else None,
        "main_camera_mp": first_mp(r, MAIN_CAM),
        "front_camera_mp": first_mp(r, SELFIE_CAM),
        "battery_mah": num(r.get("Battery_Capacity"), r"(\d+)\s*mAh"),
        "fast_charge_w": charge,
        "screen_inch": num(r.get("Display_Size"), r"(\d+(?:\.\d+)?)\s*inch"),
        "refresh_rate_hz": num(disp, r"(\d+)\s*Hz") or 60,
        "display_type": "OLED" if "OLED" in disp.upper() else "LCD",
        "weight_g": num(r.get("Body_Weight"), r"(\d+(?:\.\d+)?)\s*g\b"),
        "os": "iOS" if "ios" in os_.lower() else "Android",
        "has_5g": int("5G" in str(r.get("Network_Technology", ""))),
        "has_nfc": int(str(r.get("Connectivity_NFC", "")).strip().lower().startswith("yes")),
    }


def variants(r, prefer):
    ram = min_size(r.get("Memory_RAM")) or num(r.get("RAM"), r"(\d+)\s*GB")
    order = ["Prices_Unofficial", "Prices_Official"]
    if prefer == "official":
        order.reverse()
    for col in order:
        v = parse_variants(r.get(col), ram)
        if v:
            return v, "unofficial" if col == "Prices_Unofficial" else "official"
    p = base_price(r.get("Price"))
    sto = min_size(r.get("Memory_Internal"))
    if p and ram and sto:
        return [(ram, sto, p)], "list"
    return [], None


def official_markup(raw, min_pairs=4):
    """ڕێژەی نرخی ڕەسمی ÷ ناڕەسمی بۆ هەر براندێک (لە مۆبایلانەی کە هەردووکیان هەیە)."""
    pairs = []
    for _, r in raw.iterrows():
        off = [p for _, _, p in parse_variants(r.get("Prices_Official"), 1)]
        un = [p for _, _, p in parse_variants(r.get("Prices_Unofficial"), 1)]
        if off and un:
            ratio = min(off) / min(un)
            if 0.6 <= ratio <= 3:
                pairs.append((r["General_Brand"], ratio))
    df = pd.DataFrame(pairs, columns=["brand", "ratio"])
    overall = float(df["ratio"].median()) if len(df) else 1.3
    g = df.groupby("brand")["ratio"].agg(["median", "size"])
    per_brand = g.loc[g["size"] >= min_pairs, "median"].to_dict()
    # براندەکان کە لە بەنگلادیش فرۆشتنی ڕەسمییان هەیە
    official_brands = set(raw.loc[raw["Prices_Official"].notna(), "General_Brand"].value_counts()
                          .loc[lambda s: s >= 10].index)
    return per_brand, overall, official_brands


# براندە سەرەکییەکانی بازاڕی عێراق و کوردستان. براندەکانی تر لە داتاکەدا مۆبایلی ڕاستەقینەن،
# بەڵام یان لێرە نافرۆشرێن (براندی ناوخۆیی بەنگلادیش/هیندستان: Symphony، Walton، Helio، Lava…)
# یان تەنها 1 تا 5 مۆبایلیان هەیە (Razer، Thuraya، Leica…) کە بۆ فێربوونی مۆدێلەکە بەس نییە.
# بۆ هێشتنەوەی هەموو براندەکان:  --all-brands
MARKET_BRANDS = {
    "Apple", "Samsung", "Xiaomi", "Huawei", "Honor", "Oppo", "Realme", "Vivo", "OnePlus", "Google",
    "Motorola", "Nokia", "HMD", "Tecno", "Infinix", "Itel", "ZTE", "Sony", "Asus", "Nothing", "Lenovo",
    "TCL", "Alcatel", "LG", "HTC", "Meizu", "Blackview", "Oscal", "Doogee", "Ulefone", "Oukitel",
    "Cubot", "Umidigi",
}
# تابلێت کە لە سەرچاوەکەدا بە هەڵە وەک Smartphones نووسراون (iPad، Galaxy Tab، Xiaomi Pad…)
TABLET_RE = r"\b(?:ipad|tab|pad|matepad|tablet)\b"
FOLDABLE_RE = r"fold|flip|mate x"  # مۆبایلی پێچراوە شاشەی گەورەیان هەیە بەڵام مۆبایلن


def fix_brands(raw):
    """General_Brand هەندێک جار هەڵەیە (بۆ نموونە "Oppo A16" لە ژێر Vivo). براند لە سەرەتای ناوەکەوە."""
    brands = sorted(raw["General_Brand"].dropna().astype(str).unique(), key=len, reverse=True)
    fixed = []
    for name, brand in zip(raw["Name"].astype(str), raw["General_Brand"].astype(str)):
        low = name.lower()
        lead = next((b for b in brands if low.startswith(b.lower() + " ")), None)
        fixed.append(lead if lead and lead != brand else brand)
    changed = int((pd.Series(fixed, index=raw.index) != raw["General_Brand"].astype(str)).sum())
    raw = raw.assign(General_Brand=fixed)
    return raw, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="?", default=str(RAW))
    ap.add_argument("--rate", type=float, default=122.0, help="چەند تاکا = 1 دۆلار (2026 نزیکەی 122)")
    ap.add_argument("--min-year", type=int, default=2018,
                    help="مۆبایلی کۆنتر لابدە (نرخی مۆبایلە کۆنەکان زۆرجار کۆنن و نوێ نەکراونەتەوە)")
    ap.add_argument("--prefer", choices=["unofficial", "official"], default="unofficial")
    ap.add_argument("--no-adjust", action="store_true", help="نرخی ڕەسمی وەک خۆی بهێڵەرەوە")
    ap.add_argument("--all-brands", action="store_true", help="هەموو براندەکان بهێڵەرەوە، نەک تەنها هی بازاڕی عێراق")
    ap.add_argument("--out", default=str(ROOT / "data" / "phones.csv"))
    args = ap.parse_args()

    raw = pd.read_csv(args.raw, low_memory=False)
    n0 = len(raw)
    raw = raw[raw["General_Device"].eq("Smartphones")]
    raw = raw[raw["Launch_Status"].astype(str).str.lower().str.startswith(("available", "avaialble"))]
    raw = raw.drop_duplicates("Name")
    print(f"• {n0} ڕیز ← {len(raw)} مۆبایلی زیرەکی بەردەست (تابلێت، کاتژمێر و مۆبایلی ئاسایی لابران)")
    raw, changed = fix_brands(raw)
    print(f"• براندی {changed} مۆبایل چاک کرا (لە ناوەکەوە)")
    size = raw["Display_Size"].astype(str).str.extract(r"(\d+(?:\.\d+)?)\s*inch")[0].astype(float)
    name = raw["Name"].astype(str)
    tablet = name.str.contains(TABLET_RE, case=False, regex=True) |         ((size > 8.5) & ~name.str.contains(FOLDABLE_RE, case=False, regex=True))
    print(f"• {int(tablet.sum())} تابلێت لابران: {', '.join(name[tablet].head(6))}…")
    raw = raw[~tablet]
    if not args.all_brands:
        out_brand = ~raw["General_Brand"].isin(MARKET_BRANDS)
        dropped = raw.loc[out_brand, "General_Brand"].value_counts()
        print(f"• {int(out_brand.sum())} مۆبایل لە {len(dropped)} براندی دەرەوەی بازاڕی عێراق لابران "
              f"(زۆرترینیان: {', '.join(f'{b} {n}' for b, n in dropped.head(8).items())})")
        raw = raw[~out_brand]

    per_brand, overall, official_brands = official_markup(raw)
    if not args.no_adjust:
        print(f"• ڕێژەی نرخی ڕەسمی ÷ ناڕەسمی: گشتی {overall:.2f}، بە پێی براند: "
              + ", ".join(f"{b} {v:.2f}" for b, v in sorted(per_brand.items())))

    rows, kinds = [], {}
    for _, r in raw.iterrows():
        vs, kind = variants(r, args.prefer)
        if not vs:
            kinds["بێ نرخ"] = kinds.get("بێ نرخ", 0) + 1
            continue
        kinds[kind] = kinds.get(kind, 0) + 1
        s = specs(r)
        markup = 1.0
        if not args.no_adjust and (kind == "official" or (kind == "list" and s["brand"] in official_brands)):
            markup = per_brand.get(s["brand"], overall)
        cfg, cfg_guess = configs(r, vs)
        for ram, sto, price in vs:
            rows.append({**s, "ram_gb": ram, "storage_gb": sto, "configs": cfg, "configs_guess": cfg_guess,
                         F.TARGET: round(price / markup / args.rate), "price_bdt": price,
                         "source": f"mobiledokan.co ({kind})", "price_date": "2026"})
    out = pd.DataFrame(rows)
    print("• سەرچاوەی نرخ بە پێی مۆبایل:", kinds)

    before = len(out)
    out = out[out["release_year"].fillna(0) >= args.min_year]
    out = out[out[F.TARGET].between(40, 3000) & out["ram_gb"].between(*LIM["ram_gb"]) & out["storage_gb"].between(*LIM["storage_gb"])
              & out["ram_gb"].isin(STANDARD_RAM) & out["storage_gb"].isin(STANDARD_STORAGE)]
    out = out.drop_duplicates(["brand", "model", "ram_gb", "storage_gb"])
    print(f"• {before - len(out)} ڕیز لابران (ساڵی کۆن، نرخ یان RAM ی نائاسایی، دووبارە)")

    cols = ["brand", "model", "chipset"] + [c for c in F.ALL if c != "brand"] + \
           [F.TARGET, "price_bdt", "source", "price_date", "configs", "configs_guess"]
    out = out[cols].sort_values(["brand", "model", "ram_gb", "storage_gb"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    print(f"\n✓ {len(out)} ڕیز ({out['model'].nunique()} مۆدێل، {out['brand'].nunique()} براند) نووسرا بۆ {args.out}")
    print(f"  ڕێژەی گۆڕین: 1 USD = {args.rate:g} BDT")
    print("  ڕێژەی خانەی بەتاڵ:")
    empty = out[F.ALL].isna().mean()
    print("    " + empty[empty > 0].round(3).to_string().replace("\n", "\n    "))
    unknown = out.loc[out["chipset_tier"].isna() & out["chipset"].ne(""), "chipset"]
    if len(unknown):
        print(f"  ⚠️  {unknown.nunique()} پرۆسێسەر ئاستیان نەناسرایەوە، زۆرترینیان:")
        print("    " + unknown.value_counts().head(15).to_string().replace("\n", "\n    "))
    print("پاشان:  python -m backend.ml.train")


if __name__ == "__main__":
    main()
