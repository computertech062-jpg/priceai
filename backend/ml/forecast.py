"""
پێشبینیی نرخی مۆبایل بە پێی کات: نرخی ئەمڕۆ و نرخ دوای ساڵێک.

ڕێگا (Cohort / Analog forecasting):
  مۆبایلێک کە ئێستا تەمەنی A مانگە، نرخەکەی لە 12 مانگی داهاتوودا وەک ئەو مۆبایلە هاوشێوانە
  دەگۆڕێت کە پێشتر لە هەمان تەمەندا بوون. بۆ نموونە iPhone 17 لە تەمەنی 14 مانگیدا ← سەیری
  iPhone 12 تا 16 دەکەین کاتێک 14 مانگ بوون، و نرخیان تا 26 مانگ چەند گۆڕا.

  1. بۆ هەر مۆبایلێکی ناو data/price_history.csv زنجیرەیەکی log(نرخ) بە پێی تەمەن دروست دەکرێت
     (بنەڕەتترین جۆر کە زۆرترین ڕێکەوتی هەیە). نێوان دوو ڕێکەوت بە log-linear پڕ دەکرێتەوە، دەرەوەی
     مەودا هەرگیز نا (بێ extrapolation).
  2. گۆڕانی log(نرخ) لە تەمەنی a0 ەوە بۆ a1 بۆ هەر مۆبایلێکی هاوشێوە دەژمێردرێت.
  3. ناوەند (median) = پێشبینی، و P10–P90 = مەودا (نزیکەی 80% ی حاڵەتەکان).

  «هاوشێوە» بە ڕیزبەندی (ئەگەر کەمتر لە MIN_PEERS بوو، گرووپی فراوانتر):
     هەمان براند و هەمان بەش  ←  هەمان بەش  ←  هەموو مۆبایلەکان
  بەش: Apple ← Pro / base. براندەکانی تر ← ئاستی پرۆسێسەر (پێشەنگ 4–5، مامناوەند 3، هەرزان 1–2).

پشکنینی ڕاستی (Backtest): بۆ هەر مۆبایلێک، تەنها ئەو مۆبایلانە بەکاردێن کە پێشتر دەرچوون
(بێ زانیاری لە داهاتوو)، نرخی 12 مانگ دواتر پێشبینی دەکرێت و بە نرخی ڕاستەقینە بەراورد دەکرێت.
"""
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .history import DATA as HISTORY

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "Global_Mobile_Phone_Specifications_and_Prices_2026.csv"
MIN_PEERS = 5
HORIZON = 12
BACKTEST_AGES = (3, 6, 12, 18, 24, 36)
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}


def parse_date(text):
    """'2025, September 19' ،  'August 5, 2026' ،  '2025, October' → date"""
    s = str(text)
    m = re.match(r"\s*(20\d\d)\s*,\s*([A-Za-z]+)\s*(\d{1,2})?", s)
    if m and m.group(2).lower() in MONTHS:
        y, mo, d = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3) or 15)
    else:
        m = re.match(r"\s*([A-Za-z]+)\s+(\d{1,2}),\s*(20\d\d)", s)
        if not (m and m.group(1).lower() in MONTHS):
            return None
        y, mo, d = int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))
    try:
        return date(y, mo, d)
    except ValueError:  # هەڵەی ڕێنووس لە سەرچاوەکەدا، بۆ نموونە "February 30"
        return date(y, mo, 15)


def months_between(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.0


def segment(brand, model, tier):
    if str(brand) == "Apple":
        if re.search(r"\bSE\b|\d+e\b", str(model)):  # iPhone SE و 16e/17e
            return "apple-budget"
        # iPhone XS / XS Max مۆبایلی پێشەنگی ساڵی خۆیان بوون (پێش ناوی «Pro»)
        return "apple-pro" if re.search(r"Pro|XS", str(model)) else "apple-base"
    if tier is None or (isinstance(tier, float) and np.isnan(tier)):
        return "mid"
    return "flagship" if tier >= 4 else "mid" if tier >= 3 else "budget"


def apple_battery(model, months):
    """
    خەمڵاندنی تەندروستیی پاتری (Maximum Capacity) دوای «months» مانگ بەکارهێنان.
    Apple: iPhone 14 و کۆنتر 80% لە 500 سووڕی شەحن، iPhone 15 و نوێتر 80% لە 1000 سووڕ.
    گریمانە: ڕۆژانە یەک سووڕ، و دابەزینی هێڵی. ئەمە خەمڵاندنە، نەک داتا.
    """
    m = re.search(r"iPhone (\d+)", str(model))
    gen = int(m.group(1)) if m else 11
    rated = 1000 if gen >= 15 else 500
    cycles = 365 * months / 12
    return {"rated_cycles": rated, "cycles": round(cycles), "health_pct": round(max(60.0, 100 - 20 * cycles / rated))}


class Forecaster:
    def __init__(self, history_path=HISTORY, raw_path=RAW, today=None):
        self.today = today or date.today()
        self.series = []        # [{model, brand, segment, released, kind, ages, logp}]
        self.dates = {}         # model → {"released": date, "updated": date}
        self.available = False
        raw_path = Path(raw_path)
        if raw_path.exists():
            raw = pd.read_csv(raw_path, usecols=["Name", "Released", "General_Updated"], low_memory=False)
            for name, rel, upd in raw.drop_duplicates("Name").itertuples(index=False):
                self.dates[str(name).strip()] = {"released": parse_date(rel), "updated": parse_date(upd)}
        history_path = Path(history_path)
        if not history_path.exists():
            return
        df = pd.read_csv(history_path)
        if df.empty:
            return
        df = df[df["price_type"].isin(["unofficial", "official"]) & (df["price_usd"] > 0)]
        for (model, kind), g in df.groupby(["model", "price_type"]):
            best = None
            for _, v in g.groupby(["ram_gb", "storage_gb"], dropna=False):
                v = v.drop_duplicates("age_months").sort_values("age_months")
                if best is None or len(v) > len(best):
                    best = v
            if best is None or len(best) < 2:
                continue
            first = best.iloc[0]
            self.series.append({
                "model": model, "brand": first["brand"], "kind": kind,
                "segment": segment(first["brand"], model, first.get("chipset_tier")),
                "released": date.fromisoformat(first["release_date"]),
                "ages": best["age_months"].to_numpy(float), "logp": np.log(best["price_usd"].to_numpy(float)),
            })
        self.available = bool(self.series)
        self._backtest = None

    # ---------------------------------------------------------------- ناوەڕۆک
    @staticmethod
    def _at(s, age):
        if age < s["ages"][0] or age > s["ages"][-1]:
            return None
        return float(np.interp(age, s["ages"], s["logp"]))

    def _peer_deltas(self, a0, a1, brand, seg, before=None, exclude=None):
        """گۆڕانی log(نرخ) لە a0 بۆ a1 بۆ مۆبایلە هاوشێوەکان، لەگەڵ ناوی گرووپەکە."""
        def collect(pred):
            out = []
            for kind in ("unofficial", "official"):
                for s in self.series:
                    if s["kind"] != kind or s["model"] == exclude or not pred(s):
                        continue
                    if before and s["released"] >= before:
                        continue
                    p0, p1 = self._at(s, a0), self._at(s, a1)
                    if p0 is not None and p1 is not None:
                        out.append((s["model"], p1 - p0))
                if len(out) >= MIN_PEERS:  # بازاڕی ناڕەسمی بەسە، ڕەسمی تێکەڵ مەکە
                    break
            return out
        for scope, pred in (("brand_segment", lambda s: s["brand"] == brand and s["segment"] == seg),
                            ("segment", lambda s: s["segment"] == seg),
                            ("all", lambda s: True)):
            ds = collect(pred)
            if len(ds) >= MIN_PEERS:
                return scope, ds
        return None, []

    def _summary(self, price, ds, months):
        """
        نرخ = ناوەندی گۆڕانی هاوشێوەکان. مەودا = split-conformal: هەڵەی 80% ی Backtest
        (لە log دا)، بۆ ماوەی کورتتر بە √(مانگ/12) بچووک دەکرێتەوە (گریمانەی random walk).
        """
        v = np.array([d for _, d in ds])
        mid = price * float(np.exp(np.median(v)))
        q = self.interval_q() * np.sqrt(max(months, 0.0) / HORIZON)
        return {"price": round(mid), "low": round(mid * float(np.exp(-q))), "high": round(mid * float(np.exp(q))),
                "n": len(v)}

    def interval_q(self):
        bt = self.backtest()
        return bt.get("q_log", 0.15) if bt.get("available") else 0.15

    # ---------------------------------------------------------------- پێشبینی
    def forecast(self, model, brand, tier, price_usd, observed_date=None):
        """
        price_usd: دوایین نرخی ڕاستەقینەی ئەم جۆرە.
        observed_date: ڕێکەوتی ئەو نرخە. ئەگەر نەدرا، General_Updated ـی سەرچاوەکە (data/phones.csv).
        """
        d = self.dates.get(model, {})
        released, updated = d.get("released"), observed_date or d.get("updated")
        if not (self.available and price_usd and released):
            return {"available": False}
        updated = min(updated or self.today, self.today)
        a_obs = max(0.0, months_between(released, updated))
        a_now = max(a_obs, months_between(released, self.today))
        a_next = a_now + HORIZON
        seg = segment(brand, model, tier)
        scope_now, ds_now = self._peer_deltas(a_obs, a_now, brand, seg, exclude=model) \
            if a_now - a_obs >= 0.5 else ("same", [(model, 0.0)] * MIN_PEERS)
        scope_next, ds_next = self._peer_deltas(a_now, a_next, brand, seg, exclude=model)
        if not ds_next or not ds_now:
            return {"available": False, "reason": "no_peers", "age_months": round(a_now)}
        now = self._summary(price_usd, ds_now, a_now - a_obs)
        # دوای ساڵێک = نرخی ئەمڕۆ × گۆڕانی 12 مانگی داهاتوو (مەودا بۆ کۆی ماوەکە لە دوایین نرخی ڕاستەقینەوە)
        nxt = self._summary(now["price"], ds_next, 0)
        q = self.interval_q() * np.sqrt((a_next - a_obs) / HORIZON)
        nxt["low"], nxt["high"] = round(nxt["price"] * float(np.exp(-q))), round(nxt["price"] * float(np.exp(q)))
        yearly = np.array([dd for _, dd in ds_next])
        peers = sorted({m for m, _ in ds_next})
        out = {
            "available": True,
            "observed": {"price": round(price_usd), "date": updated.isoformat(), "age_months": round(a_obs)},
            "today": {**now, "date": self.today.isoformat(), "age_months": round(a_now)},
            "next_year": {**nxt, "date": date(self.today.year + 1, self.today.month, min(self.today.day, 28)).isoformat(),
                          "age_months": round(a_next)},
            "change_pct": round((nxt["price"] / now["price"] - 1) * 100, 1),
            "segment": seg, "scope": scope_next, "peers": peers[:8], "n_peers": len(peers),
            "peer_change_pct": {"median": round(float(np.expm1(np.median(yearly))) * 100, 1),
                                "p10": round(float(np.expm1(np.percentile(yearly, 10))) * 100, 1),
                                "p90": round(float(np.expm1(np.percentile(yearly, 90))) * 100, 1)},
            "released": released.isoformat(),
            "method": "cohort",
        }
        if brand == "Apple":
            out["battery"] = apple_battery(model, HORIZON)
        return out

    # ---------------------------------------------------------------- Backtest
    def backtest(self):
        """هەڵەی پێشبینیی 12 مانگ لەسەر نرخە ڕاستەقینەکان (تەنها مۆبایلی پێشوو وەک هاوشێوە)."""
        if self._backtest is not None:
            return self._backtest
        rows = []
        for s in self.series:
            if s["kind"] != "unofficial":
                continue
            for a0 in BACKTEST_AGES:
                p0, p1 = self._at(s, a0), self._at(s, a0 + HORIZON)
                if p0 is None or p1 is None:
                    continue
                scope, ds = self._peer_deltas(a0, a0 + HORIZON, s["brand"], s["segment"],
                                              before=s["released"], exclude=s["model"])
                if not ds:
                    continue
                v = np.array([d for _, d in ds])
                real, start = float(np.exp(p1)), float(np.exp(p0))
                pred = start * float(np.exp(np.median(v)))
                rows.append({"model": s["model"], "segment": s["segment"], "age": a0, "start": round(start),
                             "real": round(real), "ai": round(pred), "err_pct": round((pred - real) / real * 100, 1),
                             "naive_err_pct": round((start - real) / real * 100, 1),
                             "log_res": float(np.log(real / pred))})
        if not rows:
            self._backtest = {"available": False}
            return self._backtest
        df = pd.DataFrame(rows)
        # split-conformal: نیوەی مۆبایلەکان بۆ دیاریکردنی q، نیوەکەی تر بۆ پشکنینی coverage
        models = sorted(df["model"].unique())
        rng = np.random.default_rng(42)
        calib = set(rng.permutation(models)[: len(models) // 2])
        is_cal = df["model"].isin(calib)
        q_half = float(np.quantile(df.loc[is_cal, "log_res"].abs(), 0.8))
        held_cov = float((df.loc[~is_cal, "log_res"].abs() <= q_half).mean()) * 100
        q_log = float(np.quantile(df["log_res"].abs(), 0.8))  # بۆ پێشبینی: هەموو داتاکە
        df["in_range"] = df["log_res"].abs() <= q_log
        df = df.drop(columns="log_res")
        by_seg = {seg: {"n": int(len(g)), "mape": round(float(g["err_pct"].abs().mean()), 1)}
                  for seg, g in df.groupby("segment")}
        self._backtest = {
            "available": True, "horizon_months": HORIZON, "n": int(len(df)),
            "n_phones": int(df["model"].nunique()),
            "mape": round(float(df["err_pct"].abs().mean()), 1),
            "median_ape": round(float(df["err_pct"].abs().median()), 1),
            "naive_mape": round(float(df["naive_err_pct"].abs().mean()), 1),
            "q_log": round(q_log, 4), "interval_pct": round((float(np.exp(q_log)) - 1) * 100, 1),
            "coverage_target": 80, "coverage_heldout_pct": round(held_cov, 1),
            "by_segment": by_seg,
            "examples": df.sort_values(["model", "age"]).head(400).to_dict("records"),
        }
        return self._backtest
