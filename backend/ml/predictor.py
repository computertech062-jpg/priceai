"""
خزمەتگوزاریی پێشبینی: مۆدێلە ڕاهێنراوەکە بار دەکات و نرخ، مەودا،
ڕوونکردنەوە و مۆبایلی هاوشێوە دەگەڕێنێتەوە.
"""
import json
import math
from pathlib import Path

import joblib
import numpy as np

from . import features as F
from .catalog import Catalog
from .data import load_dataset, to_frame
from .explain import explain

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"


class FeatureError(ValueError):
    def __init__(self, field, message):
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


class SpecConflict(FeatureError):
    """تایبەتمەندییەک لەگەڵ تایبەتمەندییەکانی تر ناگونجێت (بۆ نموونە 5G لە 2017)."""


class VariantError(ValueError):
    """ئەم مۆبایلە بەم RAM و بیرگەیە بەرهەم نەهێنراوە."""

    def __init__(self, ram, storage):
        super().__init__(f"no variant {ram}GB/{storage}GB")
        self.ram = ram
        self.storage = storage


FIRST_5G_YEAR = 2019  # یەکەم مۆبایلەکانی 5G


class Predictor:
    def __init__(self, artifacts_dir=ARTIFACTS, data_path=None):
        artifacts_dir = Path(artifacts_dir)
        bundle_path = artifacts_dir / "model.joblib"
        if not bundle_path.exists():
            raise FileNotFoundError(
                "مۆدێل نەدۆزرایەوە. سەرەتا ڕایبهێنە:  python -m backend.ml.train")
        bundle = joblib.load(bundle_path)
        self.pipeline = bundle["pipeline"]
        self.background = bundle["background"]
        self.q_log = float(bundle["q_log"])
        self.alpha = float(bundle["alpha"])
        self.model_name = bundle["model_name"]
        self.uplift = bundle.get("variant_uplift")
        self.meta = json.loads((artifacts_dir / "metadata.json").read_text(encoding="utf-8"))
        df = load_dataset(data_path)
        self.catalog = Catalog(df)
        self._defaults = self._compute_defaults(df)
        self._options = {c: sorted(df[c].dropna().astype(str).unique().tolist()) for c in F.CATEGORICAL}

    # ---------- schema بۆ Frontend ----------
    def _compute_defaults(self, df):
        d = {}
        for c in F.NUMERIC:
            v = float(df[c].median())
            d[c] = int(v) if F.by_name(c).get("step", 1) >= 1 else round(v, 1)
        for c in F.BINARY:
            d[c] = int(df[c].mode().iloc[0])
        for c in F.CATEGORICAL:
            d[c] = str(df[c].mode().iloc[0])
        return d

    def schema(self):
        out = []
        for f in F.FEATURES:
            item = dict(f)
            if f["kind"] == "categorical":
                item["options"] = f.get("options") or self._options.get(f["name"], [])
                # بژاردەی نوێ کە لە داتادا هەیە زیاد بکە
                for o in self._options.get(f["name"], []):
                    if o not in item["options"]:
                        item["options"] = item["options"] + [o]
            item["default"] = self._defaults.get(f["name"])
            out.append(item)
        return {"features": out, "groups": F.GROUPS, "is_sample_data": self.meta.get("is_sample_data", False)}

    # ---------- پشکنین ----------
    def validate(self, raw):
        clean = {}
        for f in F.FEATURES:
            name = f["name"]
            v = raw.get(name, None)
            if v is None or v == "":
                clean[name] = None  # Imputer پڕی دەکاتەوە
                continue
            if f["kind"] == "numeric":
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise FeatureError(name, "دەبێت ژمارە بێت")
                if not math.isfinite(v) or v < f["min"] or v > f["max"]:
                    raise FeatureError(name, f"دەبێت لە نێوان {f['min']} و {f['max']} بێت")
            elif f["kind"] == "binary":
                if isinstance(v, str):
                    v = v.strip().lower() in ("1", "true", "yes")
                v = int(bool(v))
            else:
                v = str(v).strip()[:60]
            clean[name] = v
        return clean

    # ---------- گونجاندنی تایبەتمەندییەکان ----------
    def lock(self, feats, phone):
        """
        مۆبایلی ناو کاتالۆگ: هەموو تایبەتمەندییەکان لە داتاکەوە دێن و ناگۆڕدرێن.
        تەنها RAM و بیرگە هەڵدەبژێردرێن، و دەبێت یەکێک بن لە جۆرە ڕاستەقینەکانی ئەم مۆبایلە.
        """
        locked = {**feats, **{k: phone["specs"].get(k) for k in F.ALL if k not in ("ram_gb", "storage_gb")}}
        ram, sto = locked.get("ram_gb"), locked.get("storage_gb")
        if ram is None or sto is None or not self.catalog.config_allowed(phone["id"], ram, sto):
            raise VariantError(ram, sto)
        return locked

    @staticmethod
    def consistent(feats):
        """مۆبایلی تایبەت (دەستی): ئەو تایبەتمەندییانەی پێکەوە مەحاڵن ڕێگە پێنادرێن."""
        brand = feats.get("brand")
        if brand:  # سیستەم بە پێی براند: تەنها Apple ـ iOS ی هەیە
            feats["os"] = "iOS" if str(brand).strip().lower() == "apple" else "Android"
        year = feats.get("release_year")
        if feats.get("has_5g") == 1 and year is not None and year < FIRST_5G_YEAR:
            raise SpecConflict("has_5g", f"5G پێش {FIRST_5G_YEAR} نەبوو")
        return feats

    # ---------- پێشبینی ----------
    def predict_many(self, rows):
        X = to_frame(rows)
        log_pred = self.pipeline.predict(X)
        out = []
        for lp in log_pred:
            out.append({
                "price": round(float(np.expm1(lp))),
                "low": round(float(np.expm1(lp - self.q_log))),
                "high": round(float(np.expm1(lp + self.q_log))),
            })
        return out

    def _anchor(self, feats, phone_id):
        """
        بۆ مۆبایلی ناو کاتالۆگ: نرخی جۆری بنەڕەت (کەمترین بیرگە) پێشبینی دەکرێت، پاشان
        جیاوازیی RAM/بیرگە بە ڕێژەی جۆرەکانی هەمان مۆبایل زیاد دەکرێت (بڕوانە train.variant_uplift).
        دەگەڕێنێتەوە: (تایبەتمەندیی جۆری بنەڕەت، {ram_gb: Δlog, storage_gb: Δlog}) یان None.
        """
        p = self.catalog.by_id.get(phone_id) if phone_id else None
        if not p or not self.uplift or not p["variants"]:
            return None
        ram, sto = feats.get("ram_gb"), feats.get("storage_gb")
        base = min(p["variants"], key=lambda v: (v["storage_gb"] or 0, v["ram_gb"] or 0))
        if not (ram and sto and base["ram_gb"] and base["storage_gb"]):
            return None
        delta = {"ram_gb": self.uplift["ram"] * math.log2(ram / base["ram_gb"]),
                 "storage_gb": self.uplift["storage"] * math.log2(sto / base["storage_gb"])}
        return {**feats, "ram_gb": base["ram_gb"], "storage_gb": base["storage_gb"]}, delta

    def predict(self, raw, asked_price=None, with_explanation=True, with_similar=True, exclude_id=None,
                phone_id=None):
        feats = self.validate(raw)
        phone = self.catalog.by_id.get(phone_id) if phone_id else None
        feats = self.lock(feats, phone) if phone else self.consistent(feats)
        anchor = self._anchor(feats, phone_id)
        X = to_frame([anchor[0] if anchor else feats])
        lp = float(self.pipeline.predict(X)[0])
        if anchor:
            lp += sum(anchor[1].values())
        price = float(np.expm1(lp))
        low = float(np.expm1(lp - self.q_log))
        high = float(np.expm1(lp + self.q_log))
        result = {
            "price": round(price),
            "low": round(low),
            "high": round(high),
            "confidence": round((1 - self.alpha) * 100),
            "model": self.model_name,
            "is_sample_data": self.meta.get("is_sample_data", False),
            "features": feats,
            "verdict": self.verdict(price, low, high, asked_price),
        }
        if with_explanation:
            phi, base, method = explain(self.pipeline, X, self.background)
            base_price = float(np.expm1(base))
            # مۆدێل لە log ـدا کار دەکات، بۆیە phi ـەکان کۆ دەکرێنەوە بۆ log(نرخ) − log(ناوەند).
            # بۆ ئەوەی دۆلارەکانیش کۆ بکرێنەوە بۆ (نرخ − ناوەند)، هەر phi یەک بە ناوەندی لۆگاریتمیی
            # هەردوو نرخەکە لێک دەدرێت: Σ usd = L × Σ phi = نرخ − ناوەند.
            a, b = price + 1, base_price + 1
            log_mean = (a - b) / math.log(a / b) if abs(a - b) > 1e-6 else a
            items = []
            for name, p in zip(F.ALL, phi):
                if anchor:
                    p = p + anchor[1].get(name, 0.0)
                items.append({
                    "feature": name,
                    "value": feats.get(name),
                    "phi": round(float(p), 5),
                    "pct": round((math.exp(p) - 1) * 100, 1),
                    "usd": round(float(p) * log_mean, 1),
                })
            items.sort(key=lambda r: -abs(r["phi"]))
            result["explanation"] = {"method": method, "base_price": round(base_price), "items": items}
        if with_similar:
            filled = {k: (v if v is not None else self._defaults.get(k)) for k, v in feats.items()}
            result["similar"] = self.catalog.similar(filled, price, exclude_id=exclude_id)
        return result

    @staticmethod
    def verdict(price, low, high, asked):
        """ئایا ئەو نرخەی پێت وتراوە گرانە؟ بە پێی مەودای 90%."""
        if asked is None:
            return None
        try:
            asked = float(asked)
        except (TypeError, ValueError):
            return None
        if asked <= 0:
            return None
        diff = (asked - price) / price * 100
        if asked > high:
            status = "expensive"
        elif asked < low:
            status = "cheap"
        else:
            status = "fair"
        return {"asked": round(asked, 2), "diff_pct": round(diff, 1), "status": status}

    def model_info(self):
        return self.meta
