"""
کاتالۆگی مۆبایلەکان: گەڕان بە ناو (پڕکردنەوەی خۆکار) و دۆزینەوەی مۆبایلی هاوشێوە.
"""
import difflib
import math
import re
import unicodedata

import numpy as np
import pandas as pd

from . import features as F

# تایبەتمەندییەکان کە لە نێوان جۆرەکانی (variants) یەک مۆدێلدا دەگۆڕێن
VARIANT_FIELDS = ["ram_gb", "storage_gb"]


def normalize(text):
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = text.replace("+", " plus ")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        if math.isnan(v):
            return None
        return int(v) if float(v).is_integer() else round(float(v), 2)
    return v


class Catalog:
    def __init__(self, df):
        self.phones = []
        self.by_id = {}
        df = df.copy()
        df["_name"] = (df["brand"].fillna("") + " " + df["model"]).str.strip()
        seen = {}
        for (brand, model), g in df.groupby(["brand", "model"], sort=False, dropna=False):
            name = model if str(model).lower().startswith(str(brand).lower()) else f"{brand} {model}"
            pid = slugify(name) or "phone"
            seen[pid] = seen.get(pid, 0) + 1
            if seen[pid] > 1:
                pid = f"{pid}-{seen[pid]}"
            first = g.iloc[0]
            specs = {c: _clean(first[c]) for c in F.ALL if c not in VARIANT_FIELDS}
            variants = []
            for _, r in g.sort_values(VARIANT_FIELDS).iterrows():
                v = {"ram_gb": _clean(r["ram_gb"]), "storage_gb": _clean(r["storage_gb"]),
                     "price_usd": _clean(r[F.TARGET])}
                # نرخی بازاڕ: سەرچاوە و بەروار (ئەگەر لە داتاکەدا هەبن)
                for extra in ("source", "price_date", "n_sources"):
                    if extra in r.index:
                        v[extra] = _clean(r[extra])
                variants.append(v)
            phone = {
                "id": pid, "name": name, "brand": _clean(brand), "model": model,
                "chipset": first.get("chipset", "") or "", "specs": specs, "variants": variants,
                "configs": self._configs(first, variants),
                "_norm": normalize(name), "_compact": normalize(name).replace(" ", ""),
                "_tokens": normalize(name).split(),
            }
            self.phones.append(phone)
            self.by_id[pid] = phone

        # بۆ دۆزینەوەی هاوشێوە: هەر variant ێک ڕیزێکە
        rows = []
        for p in self.phones:
            for v in p["variants"]:
                rows.append({**p["specs"], **{k: v[k] for k in VARIANT_FIELDS}, "id": p["id"],
                             "price_usd": v["price_usd"]})
        self._rows = pd.DataFrame(rows)
        self._vec, self._center, self._scale = self._vectors(self._rows, fit=True)

    @staticmethod
    def _configs(row, variants):
        """
        ئەو جۆرانەی (RAM + بیرگە) ئەم مۆبایلە بەڕاستی پێیان دێت.
        هەر یەکێک: {ram_gb, storage_gb, verified, price_usd?, source?, ...}
          verified=False واتە خەمڵێنراوە (بڕوانە scripts/convert_mobiledokan.configs).
        ئەگەر ستوونی configs نەبوو (داتای نموونەیی)، تەنها جۆرە نرخدارەکان.
        """
        found = {}

        def add(text, verified):
            if not isinstance(text, str):
                return
            for part in text.split("|"):
                try:
                    ram, sto = (float(x) for x in part.split("x"))
                except ValueError:
                    continue
                found.setdefault((_clean(ram), _clean(sto)), verified)

        add(row.get("configs"), True)
        add(row.get("configs_guess"), False)
        priced = {(v["ram_gb"], v["storage_gb"]): v for v in variants}
        for key in priced:
            found[key] = True
        out = []
        for (ram, sto), verified in sorted(found.items()):
            c = {"ram_gb": ram, "storage_gb": sto, "verified": verified}
            if (ram, sto) in priced:
                c.update({k: v for k, v in priced[(ram, sto)].items() if k not in c})
            out.append(c)
        return out

    def config_allowed(self, pid, ram, storage):
        p = self.by_id.get(pid)
        if not p:
            return False
        return any(float(c["ram_gb"]) == float(ram) and float(c["storage_gb"]) == float(storage)
                   for c in p["configs"])

    # ---------- گەڕان ----------
    def search(self, q, limit=8):
        nq = normalize(q)
        if not nq:
            return []
        cq = nq.replace(" ", "")
        qt = nq.split()
        scored = []
        for p in self.phones:
            comp = p["_compact"]
            if comp == cq:
                s = 100
            elif comp.endswith(cq) or comp.startswith(cq):
                s = 92
            elif cq in comp:
                s = 85
            elif all(any(t.startswith(x) or x in t for t in p["_tokens"]) for x in qt):
                s = 78
            else:
                r = max(difflib.SequenceMatcher(None, cq, comp).ratio(),
                        max((difflib.SequenceMatcher(None, cq, t).ratio() for t in p["_tokens"]), default=0))
                s = r * 70
            if s >= 45:
                # کورتترین ناو لە پێشەوە (Galaxy A55 پێش Galaxy A55 Pro)
                scored.append((s, -len(comp), p))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [self.public(p, brief=True) for _, _, p in scored[:limit]]

    def get(self, pid):
        p = self.by_id.get(pid)
        return self.public(p) if p else None

    def brands(self):
        """براندەکان بە پێی ژمارەی مۆبایلەکانیان (زۆرترین لە سەرەوە)."""
        counts = {}
        for p in self.phones:
            if p["brand"]:
                counts[p["brand"]] = counts.get(p["brand"], 0) + 1
        return sorted(counts, key=lambda b: (-counts[b], b))

    @staticmethod
    def public(p, brief=False):
        out = {"id": p["id"], "name": p["name"], "brand": p["brand"], "chipset": p["chipset"],
               "release_year": p["specs"].get("release_year"),
               "variants": p["variants"], "configs": p["configs"]}
        if not brief:
            out["specs"] = p["specs"]
        return out

    # ---------- هاوشێوە ----------
    def _vectors(self, frame, fit=False):
        cols = [c for c in F.NUMERIC] + F.BINARY
        m = frame.reindex(columns=cols).apply(pd.to_numeric, errors="coerce").astype(float)
        for c in ("ram_gb", "storage_gb", "main_camera_mp", "battery_mah"):
            m[c] = np.log2(m[c].clip(lower=1))
        m["oled"] = (frame.get("display_type") == "OLED").astype(float)
        if fit:
            center = m.median()
            scale = m.std().replace(0, 1).fillna(1)
        else:
            center, scale = self._center, self._scale
        v = ((m - center) / scale).fillna(0.0)
        v["chipset_tier"] *= 2.0  # پرۆسێسەر گرنگترە
        return v.to_numpy(), center, scale

    def similar(self, features, predicted_price, exclude_id=None, k=4):
        if self._rows.empty:
            return []
        vec, _, _ = self._vectors(pd.DataFrame([features]))
        d = np.sqrt(((self._vec - vec) ** 2).sum(axis=1))
        price_gap = np.abs(np.log(self._rows["price_usd"].astype(float).to_numpy()) - math.log(max(predicted_price, 1)))
        score = d + 3.0 * price_gap
        order = np.argsort(score)
        out, used = [], set()
        for i in order:
            r = self._rows.iloc[i]
            if r["id"] == exclude_id or r["id"] in used:
                continue
            used.add(r["id"])
            p = self.by_id[r["id"]]
            out.append({"id": p["id"], "name": p["name"], "brand": p["brand"],
                        "ram_gb": _clean(r["ram_gb"]), "storage_gb": _clean(r["storage_gb"]),
                        "price_usd": _clean(r["price_usd"])})
            if len(out) >= k:
                break
        return out
