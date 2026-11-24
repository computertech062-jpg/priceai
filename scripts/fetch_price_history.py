"""
کۆکردنەوەی مێژووی نرخی مۆبایل لە Wayback Machine (archive.org).

بۆچی؟ data/phones.csv تەنها نرخی ئێستای تێدایە (2026). بۆ ئەوەی بزانین نرخی مۆبایلێک
دوای ساڵێک یان زیاتر چۆن دەگۆڕێت و بۆچی، پێویستمان بە نرخی هەمان مۆبایل لە کاتی جیاوازدا هەیە.
archive.org وێنەی کۆنی پەڕەکانی mobiledokan.co ی هەڵگرتووە (2019 تا 2026)، واتە هەمان
سەرچاوەی داتاکەی ئێستا، بۆیە نرخەکان ڕاستەوخۆ بەراورد دەکرێن.

چی دەکات:
  1. بۆ هەر مۆبایلێکی ناو data/phones.csv، لیستی وێنە کۆنەکانی پەڕەکەی لە archive.org وەردەگرێت (CDX API).
  2. هەر وێنەیەک (هەر مانگێک یەکێک) دادەبەزێنێت و نرخی Official و Unofficial ی هەر جۆرێک (RAM + بیرگە) دەردەهێنێت.
  3. وێنەکانی پێش ڕێکەوتی دەرچوون لادەبرێن (ئەوانە نرخی چاوەڕوانکراون، نەک نرخی ڕاستەقینە).
  4. نرخ بە پێی نرخی دۆلاری هەمان مانگ دەگۆڕدرێت بۆ USD (تاکای بەنگلادیش لە 2022–2024 زۆر دابەزی،
     بۆیە بەبێ ئەمە دابەزینی دراو وەک بەرزبوونی نرخ دەردەکەوێت).
  5. ئەنجام: data/price_history.csv — هەر ڕیزێک = یەک نرخ بۆ یەک جۆری مۆبایل لە یەک ڕێکەوتدا.

هەموو وەڵامەکان لە data/history_cache/ هەڵدەگیرێن، بۆیە ئەگەر ڕاگیرا دووبارە ڕایبکەرەوە و
لە شوێنی خۆی بەردەوام دەبێت.

بەکارهێنان:
    python scripts/fetch_price_history.py --limit 50      # تاقیکردنەوە لەسەر 50 مۆبایل
    python scripts/fetch_price_history.py                 # هەموو مۆبایلەکان (چەند کاتژمێرێک)
    python scripts/fetch_price_history.py --models "Apple iPhone 13,Samsung Galaxy A54"
    python scripts/fetch_price_history.py --build-only    # تەنها CSV لە cache ـەوە دروست بکەرەوە
"""
import argparse
import gzip
import json
import random
import re
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html import unescape
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from convert_mobiledokan import RAW, STANDARD_RAM, STANDARD_STORAGE, VARIANT_RE, taka  # noqa: E402

PHONES = ROOT / "data" / "phones.csv"
CACHE = ROOT / "data" / "history_cache"
OUT = ROOT / "data" / "price_history.csv"
USER_AGENT = "PriceAI-research/1.0 (university project; price history study)"

# نرخی 1 دۆلار بە تاکای بەنگلادیش (تێکڕای مانگانەی نزیکەیی، Bangladesh Bank).
# مانگێک کە لێرە نییە، نزیکترین مانگی پێشووی بەکاردێت.
FX_BDT = {
    "2018-01": 83.9, "2019-01": 84.5, "2020-01": 84.8,
    "2021-01": 84.8, "2021-08": 85.2, "2021-09": 85.4, "2021-10": 85.6, "2021-11": 85.8, "2021-12": 86.0,
    "2022-01": 86.0, "2022-03": 86.2, "2022-04": 86.3, "2022-05": 87.5, "2022-06": 92.5, "2022-07": 94.5,
    "2022-08": 95.0, "2022-09": 101.5, "2022-10": 103.0, "2022-11": 104.0, "2022-12": 104.5,
    "2023-01": 105.0, "2023-02": 106.0, "2023-03": 106.5, "2023-04": 107.5, "2023-05": 108.0,
    "2023-06": 108.5, "2023-07": 108.8, "2023-08": 109.5, "2023-09": 110.0, "2023-10": 110.5,
    "2023-11": 110.5, "2023-12": 110.0,
    "2024-01": 110.0, "2024-05": 117.0, "2024-06": 117.5, "2024-07": 117.9, "2024-08": 119.0,
    "2024-09": 119.5, "2024-10": 119.6, "2024-11": 119.8, "2024-12": 120.0,
    "2025-01": 122.0, "2026-01": 122.0,
}
_FX_KEYS = sorted(FX_BDT)


def fx(ym):
    """'2023-07' → 108.8"""
    best = _FX_KEYS[0]
    for k in _FX_KEYS:
        if k <= ym:
            best = k
    return FX_BDT[best]


MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}


def release_date(text):
    """'2025, March 26' → date(2025,3,26) ،  '2025, October' → date(2025,10,15) ،  '2021' → None"""
    m = re.match(r"\s*(20\d\d)\s*,\s*([A-Za-z]+)\s*(\d{1,2})?", str(text))
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return date(int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3) or 15))


# ---------------------------------------------------------------- HTTP

class Http:
    """
    داواکاری بۆ archive.org بە ڕێزەوە.
    - پەیوەندییەکان دووبارە بەکاردێنەوە (keep-alive)، چونکە archive.org پەیوەندیی نوێی زۆر ڕەت دەکاتەوە.
    - سنووری خێرایی بۆ هەموو thread ـەکان پێکەوە.
    - ئەگەر ڕەتکرایەوە (429 یان connection refused)، هەموو thread ـەکان پێکەوە چاوەڕێ دەکەن.
    """

    def __init__(self, per_second=1.0):
        self.gap = 1.0 / per_second
        self.lock = threading.Lock()
        self.next_at = 0.0
        self.local = threading.local()

    def _session(self):
        if not hasattr(self.local, "s"):
            self.local.s = requests.Session()
            self.local.s.headers.update({"User-Agent": USER_AGENT})
        return self.local.s

    def _wait(self):
        with self.lock:
            now = time.monotonic()
            at = max(now, self.next_at)
            self.next_at = at + self.gap
        time.sleep(max(0.0, at - now))

    def _cool_down(self, seconds):
        with self.lock:
            self.next_at = max(self.next_at, time.monotonic() + seconds)

    def get(self, url, tries=6):
        delay = 20.0
        for attempt in range(tries):
            self._wait()
            try:
                r = self._session().get(url, timeout=(15, 90))
                if r.status_code == 404:
                    return None
                if r.status_code == 200:
                    body = r.content
                    if body[:2] == bytes([0x1F, 0x8B]):  # archive.org هەندێک جار پەڕەی gzip وەک خۆی دەگەڕێنێتەوە
                        body = gzip.decompress(body)
                    return body.decode("utf-8", errors="ignore")
                if r.status_code not in (429, 500, 502, 503, 504):
                    r.raise_for_status()
            except requests.ConnectionError:
                self.local.__dict__.pop("s", None)  # پەیوەندییەکی نوێ
            except requests.Timeout:
                pass
            if attempt == tries - 1:
                raise ConnectionError(f"archive.org وەڵامی نەدایەوە: {url}")
            self._cool_down(delay)
            delay = min(delay * 2, 300)
        return None


# ---------------------------------------------------------------- خوێندنەوەی پەڕە

STOP = re.compile(r"^(Brand:|Launch|Global price|Expected price|Specifications|Key Specs)", re.I)
HEADLINE = re.compile(r"^৳\s*[\d,]+\.\d\d$")


def page_lines(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S | re.I)
    txt = unescape(re.sub(r"<[^>]+>", "\n", t))
    return [l.strip() for l in txt.split("\n") if l.strip()]


def parse_variants(line, default_ram=None):
    """'(8GB+128GB) ৳63,999' ،  '8GB 128GB  ৳ 61,199' ،  '(128GB) USA ৳82,500' → [(ram, storage, tag, taka)]"""
    s = re.sub(r"[()]", " ", line).replace("+", " ")
    s = re.sub(r"৳\s+", "৳", s)
    s = re.sub(r"(\d)\s+(GB|TB)\b", r"\1\2", s, flags=re.I)
    out = []
    for ram, sto, unit, tag, price in VARIANT_RE.findall(s):
        ram = float(ram) if ram else default_ram
        sto = float(sto) * (1024 if unit.upper() == "TB" else 1)
        if sto not in STANDARD_STORAGE or (ram is not None and ram not in STANDARD_RAM):
            continue
        out.append((ram, sto, tag or "", taka(price)))
    return out


def parse_page(html, default_ram=None):
    """
    نرخەکانی پەڕەیەکی mobiledokan دەردەهێنێت.
    دەگەڕێنێتەوە: {"official": {(ram, sto): taka}, "unofficial": {...}, "list": taka یان None}
    دوو شێوەی پەڕە هەیە:
      2021–2023:  Variant: | Official | (8GB+128GB) ৳63,999 | Unofficial | (8GB+128GB) ৳37,000 | Brand:
      2024–2026:  Official | <ڕوونکردنەوە> | 8GB 128GB ৳61,199 | Unofficial | <ڕوونکردنەوە> | 8GB+128GB ৳36,000 / ...
    """
    lines = page_lines(html)
    start = next((i for i, l in enumerate(lines) if HEADLINE.match(l)), None)
    res = {"official": {}, "unofficial": {}, "list": None}
    if start is None:
        return res
    # نرخی سەرەکیی پەڕەکە (تەنها کاتێک بەکاردێت کە نرخی جۆرەکان نەبوو)
    heads = []
    for l in lines[start:start + 6]:
        if HEADLINE.match(l):
            heads.append(taka(re.sub(r"[^\d,]", "", l.split(".")[0])))
        elif heads:
            break
    res["list"] = heads[-1] if heads else None  # یەکەمیان نرخی کۆنی خەتلێدراوە، دوایین نرخی ئێستایە
    # 2024+: بەشی Official/Unofficial دوورترە لە سەرەوەی پەڕەکە
    state, raw = None, {"official": {}, "unofficial": {}}
    for l in lines[start:start + 120]:
        low = l.lower()
        if low in ("official", "unofficial"):
            state = low
            continue
        if STOP.match(l):
            if any(raw.values()):
                break
            state = None
            continue
        if state and "৳" in l:
            for ram, sto, tag, p in parse_variants(l, default_ram):
                raw[state].setdefault((ram, sto), []).append((tag, p))
    for kind, d in raw.items():
        for key, prices in d.items():
            uae = [p for tag, p in prices if tag == "UAE"]
            plain = [p for tag, p in prices if not tag]
            # ڕیزبەندی: UAE (وەک convert_mobiledokan.py) ← نرخی بێ نیشانەی دوکانی ناوخۆ ← هەر نرخێکی تر.
            # نرخی «USA / JP» لە پێش نییە: بۆ نموونە iPhone 14+ ی ئەمریکی تەنها eSIM ـە و هەرزانترە.
            # ئەگەر هەمان جۆر دوو جار نووسرابوو: هەرزانترین.
            res[kind][key] = float(min(uae or plain or [p for _, p in prices]))
    return res


# ---------------------------------------------------------------- کاش

class Cache:
    def __init__(self, path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.data = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[rec["key"]] = rec["value"]

    def get(self, key):
        return self.data.get(key)

    def __contains__(self, key):
        return key in self.data

    def put(self, key, value):
        with self.lock:
            self.data[key] = value
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- کۆکردنەوە

def list_snapshots(http, cdx_cache, url, since):
    if url in cdx_cache:
        return cdx_cache.get(url)
    q = urllib.parse.urlencode({
        "url": re.sub(r"^https?://", "", url), "output": "json", "fl": "timestamp,statuscode",
        "filter": "statuscode:200", "collapse": "timestamp:6", "from": str(since.year)})
    body = http.get("https://web.archive.org/cdx/search/cdx?" + q)
    rows = json.loads(body)[1:] if body and body.strip() else []
    stamps = [r[0] for r in rows]
    cdx_cache.put(url, stamps)
    return stamps


def pick_snapshots(stamps, released, max_n):
    """تەنها دوای دەرچوون، و بە یەکسانی بەسەر کاتدا دابەش بکە (یەکەم و دوایین هەمیشە دەمێنن)."""
    after = [s for s in stamps if date(int(s[:4]), int(s[4:6]), int(s[6:8])) >= released]
    if len(after) <= max_n:
        return after
    idx = sorted({round(i * (len(after) - 1) / (max_n - 1)) for i in range(max_n)})
    return [after[i] for i in idx]


def fetch_phone(http, cdx_cache, snap_cache, phone, max_snaps):
    stamps = list_snapshots(http, cdx_cache, phone["url"], phone["released"])
    chosen = pick_snapshots(stamps, phone["released"], max_snaps)
    for ts in chosen:
        key = f"{phone['url']}@{ts}"
        if key in snap_cache:
            continue
        html = http.get(f"https://web.archive.org/web/{ts}id_/{phone['url']}")
        parsed = parse_page(html, phone["default_ram"]) if html else None
        snap_cache.put(key, None if parsed is None else {
            "official": [[k[0], k[1], v] for k, v in parsed["official"].items()],
            "unofficial": [[k[0], k[1], v] for k, v in parsed["unofficial"].items()],
            "list": parsed["list"]})
    return len(stamps), len(chosen)


def load_phones():
    """مۆبایلەکانی ناو data/phones.csv، لەگەڵ URL و ڕێکەوتی دەرچوون لە داتا خاوەکەوە."""
    have = pd.read_csv(PHONES, usecols=["brand", "model", "ram_gb", "chipset_tier", "release_year"])
    first = have.groupby("model").agg(brand=("brand", "first"), ram=("ram_gb", "min"),
                                      n_ram=("ram_gb", "nunique"), tier=("chipset_tier", "first"))
    raw = pd.read_csv(RAW, low_memory=False, usecols=["Name", "URL", "Released"])
    raw = raw.drop_duplicates("Name").set_index("Name")
    phones = []
    for model, row in first.iterrows():
        if model not in raw.index or not str(raw.at[model, "URL"]).startswith("http"):
            continue
        rel = release_date(raw.at[model, "Released"])
        if rel is None:
            continue
        # Apple نرخەکانی بەبێ RAM دەنووسێت ("(128GB) ৳81,000")؛ ئەگەر مۆبایلەکە یەک RAM ی هەیە ئەوە بەکاربهێنە
        phones.append({"model": model, "brand": row["brand"], "url": raw.at[model, "URL"], "released": rel,
                       "tier": row["tier"], "default_ram": row["ram"] if row["n_ram"] == 1 else None})
    return phones


def build_csv(phones, snap_cache, out):
    rows = []
    by_url = {}
    for key, val in snap_cache.data.items():
        url, ts = key.rsplit("@", 1)
        by_url.setdefault(url, []).append((ts, val))
    for p in phones:
        for ts, val in sorted(by_url.get(p["url"], [])):
            if not val:
                continue
            d = date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
            ym = f"{ts[:4]}-{ts[4:6]}"
            rate = fx(ym)
            age = (d.year - p["released"].year) * 12 + d.month - p["released"].month
            base = {"brand": p["brand"], "model": p["model"], "chipset_tier": p["tier"],
                    "release_date": p["released"].isoformat(), "snapshot": ts, "date": d.isoformat(),
                    "age_months": age, "bdt_per_usd": rate}
            for kind in ("unofficial", "official"):
                for ram, sto, taka_ in val[kind]:
                    rows.append({**base, "price_type": kind, "ram_gb": ram, "storage_gb": sto,
                                 "price_bdt": taka_, "price_usd": round(taka_ / rate, 2)})
            if not val["official"] and not val["unofficial"] and val["list"]:
                rows.append({**base, "price_type": "list", "ram_gb": None, "storage_gb": None,
                             "price_bdt": val["list"], "price_usd": round(val["list"] / rate, 2)})
    df = pd.DataFrame(rows)
    if len(df):
        df = df.sort_values(["brand", "model", "price_type", "ram_gb", "storage_gb", "date"])
    df.to_csv(out, index=False)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="تەنها N مۆبایلی هەڕەمەکی (بۆ تاقیکردنەوە)")
    ap.add_argument("--models", help='تەنها ئەم مۆبایلانە، بە کۆما جیاکراونەتەوە: "Apple iPhone 13,Samsung Galaxy A54"')
    ap.add_argument("--brands", help='تەنها ئەم براندانە، بە ڕیزبەندی: "Samsung,Xiaomi,Oppo"')
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--max-snaps", type=int, default=12, help="زۆرترین وێنە بۆ هەر مۆبایلێک")
    ap.add_argument("--min-year", type=int, default=2019)
    ap.add_argument("--max-year", type=int, default=2025, help="مۆبایلی نوێتر هێشتا مێژووی نییە")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--rate", type=float, default=1.0, help="زۆرترین داواکاری لە چرکەیەکدا")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    every = load_phones()
    phones = [p for p in every if args.min_year <= p["released"].year <= args.max_year]
    if args.models:
        wanted = {m.strip().lower() for m in args.models.split(",") if m.strip()}
        phones = [p for p in phones if p["model"].lower() in wanted]
    if args.brands:
        order = [b.strip().lower() for b in args.brands.split(",") if b.strip()]
        phones = sorted((p for p in phones if str(p["brand"]).lower() in order),
                        key=lambda p: (order.index(str(p["brand"]).lower()), -p["released"].year))
    if args.limit:
        random.Random(args.seed).shuffle(phones)
        phones = phones[:args.limit]
    print(f"• {len(phones)} مۆبایل (دەرچوون {args.min_year}–{args.max_year})")

    cdx_cache = Cache(CACHE / "cdx.jsonl")
    snap_cache = Cache(CACHE / "snapshots.jsonl")
    if not args.build_only:
        http = Http(args.rate)
        done, failed = 0, []
        t0 = time.time()
        with ThreadPoolExecutor(args.workers) as ex:
            futs = {ex.submit(fetch_phone, http, cdx_cache, snap_cache, p, args.max_snaps): p for p in phones}
            for f in as_completed(futs):
                p = futs[f]
                done += 1
                try:
                    total, used = f.result()
                    msg = f"{total} وێنە، {used} بەکارهات"
                except Exception as e:  # noqa: BLE001
                    failed.append(p["model"])
                    msg = f"هەڵە: {e}"
                if done % 10 == 0 or done == len(phones):
                    print(f"  [{done}/{len(phones)}] {time.time() - t0:.0f}s  {p['model']}: {msg}", flush=True)
        if failed:
            print(f"⚠️  {len(failed)} مۆبایل سەرکەوتوو نەبوو (دووبارە ڕایبکەرەوە): {', '.join(failed[:10])}")

    # CSV هەموو ئەو مۆبایلانە دەگرێتەوە کە لە cache دان، نەک تەنها ئەوانەی ئەم جارە (--limit / --models)
    df = build_csv(every, snap_cache, Path(args.out))
    if not len(df):
        print("هیچ نرخێک نەدۆزرایەوە.")
        return
    per = df.groupby("model")["date"].nunique()
    print(f"\n✓ {len(df)} ڕیز نرخ بۆ {df['model'].nunique()} مۆبایل نووسرا بۆ {args.out}")
    print(f"  مۆبایل بە 2+ ڕێکەوت: {(per >= 2).sum()}  ·  3+ ڕێکەوت: {(per >= 3).sum()}")
    print(f"  ماوەی ڕێکەوتەکان: {df['date'].min()} تا {df['date'].max()}")
    print("  جۆری نرخ:", df["price_type"].value_counts().to_dict())


if __name__ == "__main__":
    main()
