"""
ڕوونکردنەوەی پێشبینی بە Shapley values (SHAP).

دوو ڕێگا:
1. ئەگەر کتێبخانەی `shap` دامەزرابێت: TreeExplainer (بۆ Random Forest،
   Gradient Boosting، Decision Tree) یان LinearExplainer (بۆ Ridge).
2. ئەگەرنا: خەمڵاندنی Shapley بە Permutation Sampling (هەمان بیرۆکەی
   shap.PermutationExplainer) کە بۆ هەر مۆدێلێک کار دەکات.

هەردووکیان لە بۆشایی log(price) دا کار دەکەن، بۆیە:
    log_pred = base + Σ φ_i
    price    = e^base × Π e^φ_i
واتە هەر φ_i کاریگەرییەکی ڕێژەیی (%) ـە لەسەر نرخەکە.
"""
import numpy as np
import pandas as pd

from . import features as F

try:  # shap ئارەزوومەندانەیە
    import shap  # type: ignore
except Exception:  # pragma: no cover
    shap = None


def sampling_shapley(predict_log, x, background, n_perm=64, seed=0):
    """
    Monte Carlo Permutation Shapley.
    x: DataFrame ـی یەک ڕیز، background: DataFrame.
    دەگەڕێنێتەوە: (phi[M], base) بە شێوەیەک کە base + Σphi = f(x) بە تەواوی.
    """
    rng = np.random.default_rng(seed)
    cols = list(x.columns)
    m = len(cols)
    xv = x.iloc[0].to_numpy(dtype=object)
    bg = background[cols].to_numpy(dtype=object)

    rows = np.empty((n_perm * (m + 1), m), dtype=object)
    perms = []
    for k in range(n_perm):
        # Antithetic sampling: هەر دوو permutation یەک پێچەوانەی ئەوی ترە
        if k % 2 == 1:
            perm = perms[-1][::-1]
        else:
            perm = rng.permutation(m)
        perms.append(perm)
        z = bg[rng.integers(len(bg))].copy()
        base_idx = k * (m + 1)
        rows[base_idx] = z
        for j, feat in enumerate(perm, start=1):
            z = z.copy()
            z[feat] = xv[feat]
            rows[base_idx + j] = z

    frame = pd.DataFrame(rows, columns=cols)
    for c in F.NUMERIC + F.BINARY:
        if c in frame:
            frame[c] = pd.to_numeric(frame[c], errors="coerce").astype(float)
    preds = np.asarray(predict_log(frame), dtype=float).reshape(n_perm, m + 1)

    phi = np.zeros(m)
    for k, perm in enumerate(perms):
        deltas = np.diff(preds[k])
        phi[perm] += deltas
    phi /= n_perm
    fx = float(preds[0, -1])  # f(x) (هەموو ڕیزەکان لە کۆتاییدا x ن)
    base = fx - phi.sum()
    return phi, base


def _group_transformed(names_out, values):
    """کۆکردنەوەی ستوونە one-hot ـەکان بۆ تایبەتمەندیی ڕەسەن."""
    out = dict.fromkeys(F.ALL, 0.0)
    for name, v in zip(names_out, values):
        raw = name.split("__", 1)[-1]
        if raw in out:
            out[raw] += float(v)
            continue
        for c in F.CATEGORICAL:
            if raw.startswith(c + "_"):
                out[c] += float(v)
                break
    return np.array([out[c] for c in F.ALL])


def shap_library_values(pipeline, x, background):
    """ئەگەر shap هەبێت. ئەگەر هەر هەڵەیەک ڕووبدات None دەگەڕێنێتەوە."""
    if shap is None:
        return None
    try:
        pre = pipeline.named_steps["pre"]
        model = pipeline.named_steps["model"]
        names_out = pre.get_feature_names_out()
        xt = pre.transform(x)
        bt = pre.transform(background)
        kind = type(model).__name__
        if kind in ("RandomForestRegressor", "GradientBoostingRegressor", "DecisionTreeRegressor",
                    "ExtraTreesRegressor", "XGBRegressor", "LGBMRegressor"):
            explainer = shap.TreeExplainer(model, data=bt, feature_perturbation="interventional")
            method = "shap.TreeExplainer"
        elif hasattr(model, "coef_"):
            explainer = shap.LinearExplainer(model, bt)
            method = "shap.LinearExplainer"
        else:
            return None
        sv = np.asarray(explainer.shap_values(xt)).reshape(-1)
        base = float(np.ravel(explainer.expected_value)[0])
        phi = _group_transformed(names_out, sv)
        return phi, base, method
    except Exception:
        return None


def explain(pipeline, x, background, n_perm=64):
    res = shap_library_values(pipeline, x, background)
    if res is not None:
        return res
    phi, base = sampling_shapley(pipeline.predict, x, background, n_perm=n_perm)
    return phi, base, "permutation-sampling"
