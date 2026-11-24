"""
مێژووی نرخی مۆبایل: نرخە ڕاستەقینە کۆنەکانی هەمان مۆبایل لە archive.org
(دروستکراو بە scripts/fetch_price_history.py ← data/price_history.csv).

بۆ هەر مۆبایلێک و جۆرێک (RAM + بیرگە) زنجیرەیەک نرخ بە پێی کات دەگەڕێنێتەوە، لەگەڵ
پوختەیەک: نرخ لە یەکەم ڕێکەوتەوە بۆ دوایین ڕێکەوت چەند گۆڕاوە، و تێکڕای گۆڕانی ساڵانە.
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "price_history.csv"
# ڕیزبەندیی جۆری نرخ: هەمان ڕیزبەندیی data/phones.csv (بازاڕی ناڕەسمی نزیکترە لە بازاڕی عێراق)
PRICE_TYPES = ["unofficial", "official", "list"]


class PriceHistory:
    def __init__(self, path=DATA):
        path = Path(path)
        self.available = path.exists()
        self.by_model = {}
        if not self.available:
            return
        df = pd.read_csv(path)
        if df.empty:
            return
        for model, g in df.groupby("model"):
            self.by_model[model] = g.sort_values("date")

    def models(self):
        """مۆبایلەکان کە لانیکەم دوو ڕێکەوتیان هەیە."""
        return sorted(m for m, g in self.by_model.items() if g["date"].nunique() >= 2)

    def series(self, model, ram=None, storage=None):
        g = self.by_model.get(model)
        if g is None:
            return {"available": False}
        best = None
        for kind in PRICE_TYPES:
            k = g[g["price_type"] == kind]
            if k.empty:
                continue
            exact = k[(k["ram_gb"] == ram) & (k["storage_gb"] == storage)] if ram and storage else k.iloc[0:0]
            if exact.empty and storage:  # Apple: RAM نەنووسراوە
                exact = k[(k["storage_gb"] == storage) & k["ram_gb"].isna()]
            if exact["date"].nunique() >= 2:
                best = (kind, exact, True)
                break
            if best is None and k["date"].nunique() >= 2:
                # ئەم جۆرە مێژووی نییە: بچووکترین جۆر کە مێژووی هەیە
                for (r, s), v in k.groupby(["ram_gb", "storage_gb"], dropna=False, sort=True):
                    if v["date"].nunique() >= 2:
                        best = (kind, v, False)
                        break
        if best is None:
            return {"available": False}
        kind, s, exact = best
        s = s.drop_duplicates("date", keep="last")
        points = [{"date": r["date"], "age_months": int(r["age_months"]), "price_usd": round(float(r["price_usd"])),
                   "price_bdt": round(float(r["price_bdt"])), "bdt_per_usd": float(r["bdt_per_usd"])}
                  for _, r in s.iterrows()]
        first, last = points[0], points[-1]
        months = max(1, last["age_months"] - first["age_months"])
        change = last["price_usd"] / first["price_usd"] - 1
        yearly = (last["price_usd"] / first["price_usd"]) ** (12 / months) - 1
        ram_v, sto_v = s["ram_gb"].iloc[0], s["storage_gb"].iloc[0]
        return {
            "available": True,
            "price_type": kind,
            "exact_variant": exact,
            "ram_gb": None if pd.isna(ram_v) else float(ram_v),
            "storage_gb": None if pd.isna(sto_v) else float(sto_v),
            "release_date": s["release_date"].iloc[0],
            "points": points,
            "summary": {
                "from": first["date"], "to": last["date"], "months": months,
                "change_pct": round(change * 100, 1),
                "yearly_pct": round(yearly * 100, 1),
                # بە تاکا، بۆ ئەوەی کاریگەریی دراو جیا بکرێتەوە
                "change_pct_local": round((last["price_bdt"] / first["price_bdt"] - 1) * 100, 1),
            },
            "source": "archive.org (mobiledokan.co)",
        }
