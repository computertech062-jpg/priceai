"""تاقیکردنەوەی بەشی Machine Learning.   ڕاکردن:  python -m pytest -q"""
import math

import numpy as np
import pytest

from backend.ml import features as F
from backend.ml.catalog import Catalog, normalize
from backend.ml.data import load_dataset, to_frame
from backend.ml.explain import sampling_shapley
from backend.ml.predictor import FeatureError, Predictor, SpecConflict, VariantError
from backend.ml.train import conformal_quantile


@pytest.fixture(scope="module")
def predictor():
    return Predictor()


@pytest.fixture(scope="module")
def phone(predictor):
    pid = predictor.catalog.search("galaxy a55")[0]["id"]
    return predictor.catalog.get(pid)


def features_of(phone, variant=0):
    v = phone["variants"][variant]
    return {**phone["specs"], "ram_gb": v["ram_gb"], "storage_gb": v["storage_gb"]}


def test_dataset_has_all_columns():
    df = load_dataset()
    assert set(F.ALL + [F.TARGET]) <= set(df.columns)
    assert (df[F.TARGET] > 0).all()


def test_search_handles_typing_variants(predictor):
    for q in ["Galaxy A55", "samsung a 55", "GALAXY-A55"]:
        assert predictor.catalog.search(q)[0]["name"] == "Samsung Galaxy A55", q
    # "a55" چەند مۆبایلێکە (Itel, Oppo, ZTE, Samsung)، Galaxy A55 دەبێت لە ئەنجامەکاندا بێت
    assert "Samsung Galaxy A55" in [r["name"] for r in predictor.catalog.search("a55")]
    assert predictor.catalog.search("") == []
    assert predictor.catalog.search("zzzzqqq") == []


def test_normalize():
    assert normalize("  iPhone 15 Pro+ ") == "iphone 15 pro plus"


def test_prediction_and_interval(predictor, phone):
    r = predictor.predict(features_of(phone), asked_price=None)
    assert r["low"] < r["price"] < r["high"]
    assert r["confidence"] == 90
    assert r["verdict"] is None


def test_verdict_uses_interval(predictor, phone):
    r = predictor.predict(features_of(phone), with_explanation=False, with_similar=False)
    expensive = predictor.predict(features_of(phone), asked_price=r["high"] * 1.2,
                                  with_explanation=False, with_similar=False)
    cheap = predictor.predict(features_of(phone), asked_price=r["low"] * 0.8,
                              with_explanation=False, with_similar=False)
    fair = predictor.predict(features_of(phone), asked_price=r["price"],
                             with_explanation=False, with_similar=False)
    assert expensive["verdict"]["status"] == "expensive"
    assert cheap["verdict"]["status"] == "cheap"
    assert fair["verdict"]["status"] == "fair"


def test_explanation_is_additive(predictor, phone):
    feats = predictor.validate(features_of(phone))
    X = to_frame([feats])
    lp = float(predictor.pipeline.predict(X)[0])
    r = predictor.predict(feats)
    phis = sum(i["phi"] for i in r["explanation"]["items"])
    base = math.log1p(r["explanation"]["base_price"])
    assert abs(base + phis - lp) < 0.01
    assert {i["feature"] for i in r["explanation"]["items"]} == set(F.ALL)
    # دۆلارەکانیش کۆ دەبنەوە: ناوەندی داتاکە + هەموو ستوونەکان = نرخی پێشبینیکراو
    usd = sum(i["usd"] for i in r["explanation"]["items"])
    assert abs(r["explanation"]["base_price"] + usd - r["price"]) <= 3


def test_sampling_shapley_exact_for_linear_model():
    """بۆ مۆدێلێکی هێڵی، Shapley = w·(x − mean(background))."""
    import pandas as pd
    rng = np.random.default_rng(1)
    bg = pd.DataFrame(rng.normal(size=(50, 3)), columns=["a", "b", "c"])
    w = np.array([2.0, -1.0, 0.5])
    f = lambda d: d[["a", "b", "c"]].to_numpy(float) @ w  # noqa: E731
    x = pd.DataFrame([[1.0, 2.0, 3.0]], columns=["a", "b", "c"])
    phi, base = sampling_shapley(f, x, bg, n_perm=400)
    assert abs(base + phi.sum() - f(x)[0]) < 1e-9
    # هەڵەی sampling لە background ـەوە دێت، بۆیە بە تەقریبی
    expected = w * (x.to_numpy()[0] - bg.to_numpy().mean(axis=0))
    assert np.allclose(phi, expected, atol=0.35)


def test_validation_rejects_bad_values(predictor, phone):
    bad = features_of(phone)
    bad["ram_gb"] = 999
    with pytest.raises(FeatureError):
        predictor.validate(bad)
    bad["ram_gb"] = "abc"
    with pytest.raises(FeatureError):
        predictor.validate(bad)


def test_missing_values_are_imputed(predictor):
    r = predictor.predict({"brand": "Samsung", "ram_gb": 8, "storage_gb": 256},
                          with_explanation=False, with_similar=False)
    assert r["price"] > 0


def test_unknown_brand_does_not_crash(predictor, phone):
    feats = features_of(phone)
    feats["brand"] = "BrandNobodyKnows"
    assert predictor.predict(feats, with_explanation=False, with_similar=False)["price"] > 0


def test_more_storage_is_not_cheaper(predictor, phone):
    feats = features_of(phone)
    low = predictor.predict({**feats, "storage_gb": 128}, with_explanation=False, with_similar=False)
    high = predictor.predict({**feats, "storage_gb": 512}, with_explanation=False, with_similar=False)
    assert high["price"] >= low["price"]


def test_similar_excludes_self(predictor, phone):
    r = predictor.predict(features_of(phone), exclude_id=phone["id"])
    assert len(r["similar"]) > 0
    assert all(s["id"] != phone["id"] for s in r["similar"])


def test_conformal_quantile():
    res = np.arange(1, 101, dtype=float)
    q = conformal_quantile(res, 0.1)
    assert 90 <= q <= 92


def test_metadata_reports_all_models(predictor):
    names = {r["name"] for r in predictor.meta["results"]}
    assert {"Ridge Regression", "Decision Tree", "Random Forest", "Gradient Boosting"} <= names
    assert 0 <= predictor.meta["interval"]["test_coverage"] <= 1


def test_catalog_ids_unique():
    cat = Catalog(load_dataset())
    ids = [p["id"] for p in cat.phones]
    assert len(ids) == len(set(ids))


# ---------- جۆرە ڕاستەقینەکان و تایبەتمەندیی قفڵکراو ----------
def test_every_phone_has_real_configs(predictor):
    for p in predictor.catalog.phones:
        keys = {(c["ram_gb"], c["storage_gb"]) for c in p["configs"]}
        assert keys, p["name"]
        assert {(v["ram_gb"], v["storage_gb"]) for v in p["variants"]} <= keys, p["name"]


def test_catalog_phone_specs_are_locked(predictor, phone):
    fake = {**features_of(phone), "main_camera_mp": 200, "chipset_tier": 5, "has_nfc": 0, "release_year": 2015}
    r = predictor.predict(fake, phone_id=phone["id"], with_explanation=False, with_similar=False)
    for k, v in phone["specs"].items():
        assert r["features"][k] == v, k


def test_catalog_phone_rejects_unreal_variant(predictor, phone):
    real = {(c["ram_gb"], c["storage_gb"]) for c in phone["configs"]}
    assert (16, 2048) not in real
    with pytest.raises(VariantError):
        predictor.predict({**features_of(phone), "ram_gb": 16, "storage_gb": 2048}, phone_id=phone["id"])


def test_variant_steps_are_realistic(predictor):
    """دووقاتکردنی بیرگە لە هەمان مۆبایلدا نابێت نرخ زیاتر لە 25% بەرز بکاتەوە."""
    p = next(p for p in predictor.catalog.phones if len({c["storage_gb"] for c in p["configs"]
                                                          if c["ram_gb"] == p["configs"][0]["ram_gb"]}) >= 2)
    ram = p["configs"][0]["ram_gb"]
    stos = sorted(c["storage_gb"] for c in p["configs"] if c["ram_gb"] == ram)
    prices = [predictor.predict({**p["specs"], "ram_gb": ram, "storage_gb": s}, phone_id=p["id"],
                                with_explanation=False, with_similar=False)["price"] for s in stos[:2]]
    ratio = prices[1] / prices[0]
    assert 1.0 <= ratio <= 1.25 ** math.log2(stos[1] / stos[0]), (p["name"], stos, prices)


def test_custom_phone_os_follows_brand(predictor, phone):
    r = predictor.predict({**features_of(phone), "brand": "Apple", "os": "Android"},
                          with_explanation=False, with_similar=False)
    assert r["features"]["os"] == "iOS"
    r = predictor.predict({**features_of(phone), "brand": "Samsung", "os": "iOS"},
                          with_explanation=False, with_similar=False)
    assert r["features"]["os"] == "Android"


def test_custom_phone_no_5g_before_2019(predictor, phone):
    with pytest.raises(SpecConflict):
        predictor.predict({**features_of(phone), "release_year": 2017, "has_5g": 1})
    ok = predictor.predict({**features_of(phone), "release_year": 2017, "has_5g": 0},
                           with_explanation=False, with_similar=False)
    assert ok["price"] > 0


def test_configs_use_standard_sizes(predictor):
    """هەڵەی ڕێنووسی سەرچاوە (بۆ نموونە "28GB") نابێت ببێتە جۆرێک."""
    storage = {16, 32, 64, 128, 256, 512, 1024, 2048}
    ram = {1, 1.5, 2, 3, 4, 6, 8, 10, 12, 16, 18, 20, 24}
    for p in predictor.catalog.phones:
        for c in p["configs"]:
            assert c["storage_gb"] in storage and c["ram_gb"] in ram, (p["name"], c)


def test_no_tablets_or_off_market_brands(predictor):
    names = [p["name"].lower() for p in predictor.catalog.phones]
    assert not [n for n in names if "ipad" in n or " tab " in f"{n} " or " pad " in f"{n} "]
    assert not {"Razer", "Thuraya", "Symphony", "Walton", "Helio"} & set(predictor.catalog.brands())


def test_evaluation_is_grouped_by_phone(predictor):
    """Testing تەنها مۆبایلی نەبینراوە: جۆرەکانی یەک مۆبایل لێک جیا ناکرێنەوە."""
    import numpy as np
    from sklearn.model_selection import GroupShuffleSplit
    from backend.ml.train import SEED, phone_groups
    assert "grouped" in predictor.meta["method"]["split"]
    df = load_dataset()
    groups = phone_groups(df)
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(df, groups=groups))
    assert not set(groups[tr]) & set(groups[te])
    assert 0.80 <= predictor.meta["results"][-1]["test"]["r2"] or any(
        r["test"]["r2"] >= 0.80 for r in predictor.meta["results"])
