"""
ڕاهێنانی مۆدێلەکان و هەڵبژاردنی باشترین.

هەنگاوەکان:
 1. خوێندنەوەی داتا و دابەشکردن: 80% Training / 20% Testing — بە پێی مۆبایل (Grouped):
    هەموو جۆرەکانی یەک مۆبایل (بۆ نموونە 128GB و 256GB) یان لە Training ن یان لە Testing،
    بۆ ئەوەی Testing تەنها مۆبایلی نەبینراو بێت و ئەنجامەکان زیاد لە ڕاستی نەبن
 2. Target = log(1 + price) — چونکە نرخەکان skewed ن
 3. بۆ هەر ئەلگۆریتمێک: 5-fold Grouped Cross-Validation لەسەر Training (هەمان یاسای مۆبایل)
    + تاقیکردنەوەی چەند hyperparameter
 4. هەڵبژاردنی باشترین مۆدێل بە پێی CV RMSE (نەک Test، بۆ ئەوەی Test پاک بمێنێتەوە)
 5. مەودای پێشبینی بە Conformal Prediction (لە هەڵەکانی out-of-fold)
 6. هەڵسەنگاندنی کۆتایی لەسەر Test + گرینگیی تایبەتمەندییەکان (mean |SHAP|)
 7. پاشەکەوتکردن: backend/artifacts/model.joblib و metadata.json

بەکارهێنان (لە فۆڵدەری سەرەکیی پرۆژەکە):
    python -m backend.ml.train
    python -m backend.ml.train --data data/phones.csv
"""
import argparse
import itertools
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

from . import features as F
from .data import is_sample, load_dataset
from .explain import explain

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"
SEED = 42
ALPHA = 0.10  # مەودای 90%


def build_preprocessor():
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    binary = SimpleImputer(strategy="most_frequent")
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=3,
                                 sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric, F.NUMERIC),
        ("bin", binary, F.BINARY),
        ("cat", categorical, F.CATEGORICAL),
    ])


def candidates():
    """ئەلگۆریتمەکان و ئەو hyperparameter ـانەی تاقی دەکرێنەوە."""
    c = {
        "Baseline (Median)": (DummyRegressor(strategy="median"), {}),
        "Ridge Regression": (Ridge(), {"alpha": [0.1, 1.0, 10.0]}),
        "Decision Tree": (DecisionTreeRegressor(random_state=SEED),
                          {"max_depth": [6, 10], "min_samples_leaf": [2, 5]}),
        "Random Forest": (RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=-1),
                          {"min_samples_leaf": [1, 3], "max_features": [0.5, 1.0]}),
        "Gradient Boosting": (GradientBoostingRegressor(random_state=SEED, subsample=0.8),
                              {"n_estimators": [300, 600], "learning_rate": [0.05],
                               "max_depth": [2, 3]}),
    }
    try:  # ئەگەر دامەزرابێت
        from xgboost import XGBRegressor  # type: ignore
        c["XGBoost"] = (XGBRegressor(random_state=SEED, n_estimators=500, subsample=0.8,
                                     colsample_bytree=0.8, verbosity=0),
                        {"max_depth": [3, 5], "learning_rate": [0.05]})
    except Exception:
        pass
    try:
        from lightgbm import LGBMRegressor  # type: ignore
        c["LightGBM"] = (LGBMRegressor(random_state=SEED, n_estimators=500, verbose=-1),
                         {"num_leaves": [15, 31], "learning_rate": [0.05]})
    except Exception:
        pass
    return c


def make_pipeline(model):
    return Pipeline([("pre", build_preprocessor()), ("model", model)])


def dollar_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "mape": float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100),
    }


def phone_groups(df):
    """هەر مۆبایلێک (براند + مۆدێل) یەک گرووپە: جۆرەکانی لێک جیا ناکرێنەوە."""
    return (df["brand"].astype(str) + "|" + df["model"].astype(str)).to_numpy()


def cross_validate(pipe, X, y_log, kf, groups):
    """out-of-fold پێشبینییەکان (log) و RMSE ی هەر fold ێک (بە دۆلار)."""
    oof = np.zeros(len(X))
    fold_rmse = []
    for tr, va in kf.split(X, y_log, groups):
        p = clone(pipe).fit(X.iloc[tr], y_log[tr])
        oof[va] = p.predict(X.iloc[va])
        fold_rmse.append(math.sqrt(mean_squared_error(np.expm1(y_log[va]), np.expm1(oof[va]))))
    return oof, fold_rmse


def conformal_quantile(residuals, alpha):
    n = len(residuals)
    level = min(1.0, math.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(residuals, level, method="higher"))


def variant_uplift(df):
    """
    کاریگەریی RAM و بیرگە لە نێوان جۆرەکانی هەمان مۆبایلدا (نەک لە نێوان مۆبایلە جیاوازەکان).

    مۆدێلەکە کاریگەریی بیرگە لە بەراوردی مۆبایلە جیاوازەکان فێردەبێت: مۆبایلی 512GB زۆربەیان
    پێشەنگن، بۆیە وا دەزانێت 512GB خۆی نرخ زۆر بەرز دەکاتەوە. بۆ مۆبایلی ناو کاتالۆگ،
    ئەم ڕێژانە بەکاردێن: Δlog(price) = storage·Δlog2(storage) + ram·Δlog2(ram)
    """
    rows = []
    for _, g in df.groupby(["brand", "model"]):
        if len(g) < 2:
            continue
        g = g.sort_values(["storage_gb", "ram_gb"])
        base = g.iloc[0]
        for _, r in g.iloc[1:].iterrows():
            dl = math.log(r[F.TARGET] / base[F.TARGET])
            if -0.2 <= dl <= 1.5:  # نرخی هەڵە لابدە
                rows.append((math.log2(r["storage_gb"] / base["storage_gb"]),
                             math.log2(r["ram_gb"] / base["ram_gb"]), dl))
    if len(rows) < 30:
        return None
    a = np.array(rows)
    coef = np.linalg.lstsq(a[:, :2], a[:, 2], rcond=None)[0]
    coef = np.clip(coef, 0.0, 0.4)
    return {"storage": float(coef[0]), "ram": float(coef[1]), "pairs": len(rows)}


def histogram(values, bins=20):
    counts, edges = np.histogram(values, bins=bins)
    return {"counts": counts.tolist(), "edges": [round(float(e), 2) for e in edges]}


def train(data_path=None, out_dir=ARTIFACTS, verbose=True):
    t0 = time.time()
    log = print if verbose else (lambda *a, **k: None)
    df = load_dataset(data_path)
    X = df[F.ALL]
    y = df[F.TARGET].to_numpy(float)
    y_log = np.log1p(y)

    groups = phone_groups(df)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    idx_train, idx_test = next(splitter.split(X, y_log, groups))
    assert not set(groups[idx_train]) & set(groups[idx_test])  # هیچ مۆبایلێک لە هەردووکیاندا نییە
    g_tr = groups[idx_train]
    X_tr, X_te = X.iloc[idx_train], X.iloc[idx_test]
    y_tr, y_te = y[idx_train], y[idx_test]
    yl_tr = y_log[idx_train]
    log(f"داتا: {len(df)} ڕیز ({len(set(groups))} مۆبایل)  →  Training {len(X_tr)}  |  Testing {len(X_te)} "
        f"({len(set(groups[idx_test]))} مۆبایلی نەبینراو)")

    kf = GroupKFold(n_splits=5)
    results = []
    best = None
    for name, (model, grid) in candidates().items():
        keys = list(grid)
        combos = [dict(zip(keys, v)) for v in itertools.product(*grid.values())] or [{}]
        best_local = None
        for params in combos:
            pipe = make_pipeline(clone(model).set_params(**params))
            oof, fold_rmse = cross_validate(pipe, X_tr, yl_tr, kf, g_tr)
            score = float(np.mean(fold_rmse))
            if best_local is None or score < best_local["cv_rmse"]:
                best_local = {"params": params, "cv_rmse": score, "cv_rmse_std": float(np.std(fold_rmse)),
                              "oof": oof, "pipe": pipe}
        cv = dollar_metrics(y_tr, np.expm1(best_local["oof"]))
        fitted = clone(best_local["pipe"]).fit(X_tr, yl_tr)
        test = dollar_metrics(y_te, np.expm1(fitted.predict(X_te)))
        row = {
            "name": name,
            "params": best_local["params"],
            "cv": {**cv, "rmse_std": best_local["cv_rmse_std"]},
            "test": test,
        }
        results.append(row)
        log(f"  {name:<20} CV RMSE ${best_local['cv_rmse']:8.2f}   Test R² {test['r2']:.4f}  "
            f"MAE ${test['mae']:.2f}")
        if name != "Baseline (Median)" and (best is None or best_local["cv_rmse"] < best["cv_rmse"]):
            best = {**best_local, "name": name, "fitted": fitted}

    # ---- مەودای پێشبینی (Conformal) ----
    residuals = np.abs(yl_tr - best["oof"])
    q = conformal_quantile(residuals, ALPHA)
    pred_te_log = best["fitted"].predict(X_te)
    lo = np.expm1(pred_te_log - q)
    hi = np.expm1(pred_te_log + q)
    coverage = float(np.mean((y_te >= lo) & (y_te <= hi)))
    log(f"باشترین: {best['name']}  |  مەودای 90%: ±{(math.exp(q) - 1) * 100:.1f}%  |  "
        f"Coverage لەسەر Test: {coverage * 100:.1f}%")

    # ---- گرینگیی تایبەتمەندییەکان (mean |SHAP|) ----
    rng = np.random.default_rng(SEED)
    background = X_tr.iloc[rng.choice(len(X_tr), size=min(100, len(X_tr)), replace=False)].reset_index(drop=True)
    sample = X_te.iloc[rng.choice(len(X_te), size=min(60, len(X_te)), replace=False)]
    abs_phi = np.zeros(len(F.ALL))
    method = None
    for i in range(len(sample)):
        phi, _, method = explain(best["fitted"], sample.iloc[[i]], background, n_perm=32)
        abs_phi += np.abs(phi)
    abs_phi /= len(sample)
    importance = sorted(
        [{"feature": c, "value": float(v)} for c, v in zip(F.ALL, abs_phi)],
        key=lambda r: -r["value"])

    uplift = variant_uplift(df)
    if uplift:
        log(f"جیاوازیی جۆرەکانی هەمان مۆبایل ({uplift['pairs']} جووت): دووقاتکردنی بیرگە "
            f"{(math.exp(uplift['storage']) - 1) * 100:+.1f}%  |  دووقاتکردنی RAM "
            f"{(math.exp(uplift['ram']) - 1) * 100:+.1f}%")

    pred_te = np.expm1(pred_te_log)
    pts = rng.choice(len(y_te), size=min(400, len(y_te)), replace=False)
    meta = {
        "version": 1,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "train_seconds": round(time.time() - t0, 1),
        "is_sample_data": is_sample(df.attrs["path"]),
        "dataset": {
            "file": Path(df.attrs["path"]).name,
            "rows": int(len(df)),
            "dropped_rows": int(df.attrs.get("dropped", 0)),
            "models": int(df[["brand", "model"]].drop_duplicates().shape[0]),
            "brands": int(df["brand"].nunique()),
            "train_rows": int(len(X_tr)),
            "test_rows": int(len(X_te)),
            "features": len(F.ALL),
            "price": {k: float(v) for k, v in df[F.TARGET].describe().items() if k != "count"},
        },
        "method": {
            "target": "log1p(price)",
            "cv_folds": 5,
            "test_size": 0.2,
            "split": "grouped by phone model (all variants of a phone stay in the same set)",
            "selection": "lowest mean CV RMSE",
            "interval": "split-conformal on out-of-fold residuals",
            "alpha": ALPHA,
            "explanation": method,
        },
        "best_model": best["name"],
        "best_params": best["params"],
        "results": results,
        "variant_uplift": uplift,
        "interval": {"q_log": q, "pct": (math.exp(q) - 1) * 100, "test_coverage": coverage},
        "importance": importance,
        "plots": {
            "scatter": [[round(float(y_te[i]), 2), round(float(pred_te[i]), 2)] for i in pts],
            "residuals": histogram(pred_te - y_te),
        },
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": best["fitted"], "background": background, "q_log": q,
                 "alpha": ALPHA, "features": F.ALL, "model_name": best["name"],
                 "variant_uplift": uplift},
                out_dir / "model.joblib")
    (out_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"✓ پاشەکەوت کرا لە {out_dir}  ({meta['train_seconds']} چرکە)")
    return meta


def main():
    ap = argparse.ArgumentParser(description="ڕاهێنانی مۆدێلەکانی PriceAI")
    ap.add_argument("--data", help="ڕێڕەوی فایلی CSV (بنەڕەت: data/phones.csv یان داتای نموونەیی)")
    args = ap.parse_args()
    train(args.data)


if __name__ == "__main__":
    main()
