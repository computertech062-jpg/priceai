"""
دروستکردنی داتای نموونەیی (Synthetic sample data).

⚠️ گرنگ: ئەم داتایە ڕاستەقینە نییە. تەنها بۆ ئەوەیە سیستەمەکە پێش
هاتنی داتای ڕاستەقینە کار بکات و تاقی بکرێتەوە. ناو و نرخەکان دروستکراون
و پەیوەندییان بە مۆبایلی ڕاستەقینەوە نییە.

بۆ بەحسەکەت دەبێت داتای ڕاستەقینە (بۆ نموونە GSMArena لە Kaggle)
بەکاربهێنیت: بڕوانە scripts/prepare_dataset.py و README.md.

بەکارهێنان:
    python scripts/make_sample_data.py
"""
import csv
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample_phones.csv"

rng = random.Random(42)

BRAND_PREMIUM = {
    "Apple": 0.45, "Google": 0.20, "Samsung": 0.15, "OnePlus": 0.10, "Huawei": 0.10,
    "Nothing": 0.05, "Oppo": 0.00, "Xiaomi": -0.05, "Vivo": -0.02, "Honor": -0.02,
    "Motorola": -0.08, "Realme": -0.12, "Tecno": -0.25, "Infinix": -0.25,
}

# (ناوی زنجیرە، ئاستی پرۆسێسەر [کەمترین، زۆرترین]، ژمارەکان، پاشگرەکان)
SERIES = {
    "Apple": [("iPhone", (4, 5), range(11, 17), ["", " Plus", " Pro", " Pro Max"])],
    "Samsung": [("Galaxy S", (5, 5), range(20, 26), ["", "+", " Ultra"]),
                ("Galaxy A", (1, 4), range(10, 80, 5), [""]),
                ("Galaxy M", (1, 3), range(12, 56, 4), [""])],
    "Google": [("Pixel", (4, 5), range(6, 10), ["", "a", " Pro"])],
    "Xiaomi": [("Xiaomi", (4, 5), range(11, 16), ["", " Pro", "T"]),
               ("Redmi Note", (2, 3), range(9, 15), ["", " Pro", " Pro+"]),
               ("Redmi", (1, 2), range(9, 15), ["", "C", "A"])],
    "OnePlus": [("OnePlus", (4, 5), range(8, 13), ["", " Pro", "R"]),
                ("OnePlus Nord", (3, 4), range(2, 5), ["", " CE"])],
    "Oppo": [("Reno", (3, 4), range(6, 13), ["", " Pro"]),
             ("Oppo A", (1, 3), range(16, 80, 6), [""])],
    "Vivo": [("Vivo V", (3, 4), range(21, 31), ["", "e"]),
             ("Vivo Y", (1, 2), range(15, 40, 3), ["", "s"])],
    "Realme": [("Realme", (2, 4), range(8, 13), ["", " Pro", " Pro+"]),
               ("Realme C", (1, 1), range(21, 68, 4), [""])],
    "Huawei": [("Huawei P", (4, 5), range(30, 71, 10), ["", " Pro"]),
               ("Huawei Nova", (2, 3), range(8, 13), ["", "i"])],
    "Motorola": [("Moto G", (1, 3), range(10, 90, 6), ["", " Power"]),
                 ("Motorola Edge", (3, 4), range(20, 51, 10), ["", " Pro"])],
    "Honor": [("Honor", (3, 4), range(50, 91, 10), ["", " Pro", " Lite"]),
              ("Honor X", (1, 3), range(6, 10), ["a", "b", "c"])],
    "Nothing": [("Nothing Phone", (3, 4), range(1, 4), ["", "a"])],
    "Tecno": [("Tecno Spark", (1, 2), range(8, 21), ["", " Pro"]),
              ("Tecno Camon", (2, 3), range(17, 31), ["", " Pro"])],
    "Infinix": [("Infinix Hot", (1, 2), range(10, 41, 3), ["", " Play"]),
                ("Infinix Note", (2, 3), range(10, 41, 3), ["", " Pro"])],
}

CHIPSETS = {
    1: ["Helio G36", "Unisoc T606", "Snapdragon 4 Gen 1"],
    2: ["Helio G85", "Snapdragon 680", "Helio G99"],
    3: ["Dimensity 6100+", "Snapdragon 695", "Exynos 1280"],
    4: ["Dimensity 7200", "Snapdragon 7 Gen 3", "Exynos 1480", "Snapdragon 7+ Gen 2"],
    5: ["Snapdragon 8 Gen 3", "Dimensity 9300", "Snapdragon 8 Gen 2"],
}

RAM_BY_TIER = {1: [3, 4], 2: [4, 6], 3: [6, 8], 4: [8, 12], 5: [8, 12, 16]}
STORAGE_BY_TIER = {1: [32, 64], 2: [64, 128], 3: [128, 256], 4: [128, 256, 512], 5: [256, 512, 1024]}


def pick_chipset(brand, tier, year):
    if brand == "Apple":
        return f"A{min(18, 13 + (year - 2019))}{' Pro' if tier == 5 and year >= 2022 else ''} Bionic"
    if brand == "Google" and tier >= 4:
        return f"Tensor G{max(1, year - 2020)}"
    return rng.choice(CHIPSETS[tier])


def make_model(brand, series, tier_range, num, suffix, year):
    tier = rng.randint(*tier_range)
    if any(s in suffix for s in ("Pro", "Ultra", "+")) and tier < 5:
        tier += 1
    if any(s in suffix for s in ("Lite", "C", "A", "Play", "a", "e", "s")) and tier > 1:
        tier -= 1
    is_ios = brand == "Apple"
    oled_p = [0.05, 0.2, 0.55, 0.9, 1.0][tier - 1]
    spec = {
        "brand": brand,
        "model": (f"{series}{num}{suffix}" if len(series.split()[-1]) == 1 and len(series.split()) > 1
                  else f"{series} {num}{suffix}").replace("  ", " "),
        "chipset": pick_chipset(brand, tier, year),
        "release_year": year,
        "chipset_tier": tier,
        "main_camera_mp": rng.choice({1: [13, 13, 50], 2: [48, 50, 50], 3: [50, 64, 108],
                                      4: [50, 64, 108], 5: [48, 50, 200]}[tier]),
        "front_camera_mp": rng.choice({1: [5, 8], 2: [8, 13], 3: [13, 16, 32],
                                       4: [16, 32], 5: [12, 32, 40]}[tier]),
        "battery_mah": int(round(rng.gauss(4300 if is_ios else 5000, 350) / 50) * 50),
        "fast_charge_w": rng.choice({1: [10, 18], 2: [18, 25, 33], 3: [25, 33, 45],
                                     4: [33, 45, 67, 80], 5: [25, 45, 80, 100, 120]}[tier]),
        "screen_inch": round(rng.uniform(6.1, 6.8) if "Max" in suffix or "Ultra" in suffix or "+" in suffix
                             else rng.uniform(6.0, 6.7), 1),
        "refresh_rate_hz": rng.choice({1: [60, 90], 2: [90, 90, 120], 3: [90, 120], 4: [120, 120, 144],
                                       5: [120]}[tier]),
        "display_type": "OLED" if rng.random() < oled_p else "LCD",
        "weight_g": int(rng.gauss(185 + 8 * (tier - 3), 12)),
        "os": "iOS" if is_ios else "Android",
        "has_5g": int(rng.random() < min(0.98, 0.15 + 0.12 * (year - 2019) + 0.15 * (tier - 1))),
        "has_nfc": int(is_ios or rng.random() < 0.3 + 0.15 * tier),
    }
    if is_ios:
        spec["main_camera_mp"] = 48 if year >= 2022 and tier == 5 else 12
        spec["front_camera_mp"] = 12
        spec["refresh_rate_hz"] = 120 if tier == 5 and year >= 2021 else 60
        spec["fast_charge_w"] = 20 if year < 2023 else 27
    return spec


def price_for(s, model_noise):
    log_p = 4.2 + model_noise
    log_p += BRAND_PREMIUM[s["brand"]]
    log_p += 0.38 * (s["chipset_tier"] - 1)
    log_p += 0.08 * math.log2(s["storage_gb"] / 64)
    log_p += 0.05 * math.log2(s["ram_gb"] / 4)
    log_p += 0.06 * math.log2(s["main_camera_mp"] / 12)
    log_p += 0.04 * (s["refresh_rate_hz"] >= 120)
    log_p += 0.07 * (s["display_type"] == "OLED")
    log_p += 0.05 * s["has_5g"] + 0.03 * s["has_nfc"]
    log_p += 0.035 * (s["release_year"] - 2019)
    log_p += 0.0015 * (s["fast_charge_w"] - 18)
    log_p += rng.gauss(0, 0.03)
    return round(math.exp(log_p) / 5) * 5 - 1  # نرخێکی وەک 399$


def main():
    rows = []
    for brand, series_list in SERIES.items():
        for series, tier_range, nums, suffixes in series_list:
            for i, num in enumerate(nums):
                year = min(2025, 2019 + int(i * 6 / max(1, len(nums) - 1)))
                for suffix in suffixes:
                    if rng.random() < 0.25:
                        continue
                    spec = make_model(brand, series, tier_range, num, suffix, year)
                    tier = spec["chipset_tier"]
                    combos = sorted({(r, st) for r in RAM_BY_TIER[tier] for st in STORAGE_BY_TIER[tier]
                                     if st >= r * 8})
                    rng.shuffle(combos)
                    model_noise = rng.gauss(0, 0.12)
                    for ram, storage in sorted(combos[: rng.randint(1, 3)]):
                        row = dict(spec, ram_gb=6 if spec["os"] == "iOS" and tier < 5 else (8 if spec["os"] == "iOS" else ram),
                                   storage_gb=storage)
                        row["price_usd"] = price_for(row, model_noise)
                        rows.append(row)
    cols = ["brand", "model", "chipset", "release_year", "ram_gb", "storage_gb", "chipset_tier",
            "main_camera_mp", "front_camera_mp", "battery_mah", "fast_charge_w", "screen_inch",
            "refresh_rate_hz", "display_type", "weight_g", "os", "has_5g", "has_nfc", "price_usd"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})
    print(f"✓ {len(rows)} ڕیز نووسرا بۆ {OUT}")


if __name__ == "__main__":
    main()
