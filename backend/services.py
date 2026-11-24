"""
لۆجیکی سەربەخۆ لە بنکەی زانیاری: گۆڕینی تۆمارەکان بۆ JSON و دروستکردنی ئامارەکانی داشبۆرد.
ئەم فەنکشنانە لەگەڵ هەر ئۆبجێکتێک کار دەکەن کە هەمان attribute ـەکانی هەبێت.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone


def iso(dt):
    return dt.replace(microsecond=0).isoformat() + "Z" if dt else None


def user_out(u):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role,
            "is_active": bool(u.is_active), "created_at": iso(u.created_at)}


def prediction_out(p, full=False):
    out = {
        "id": p.id, "phone_id": p.phone_id, "phone_name": p.phone_name, "brand": p.brand,
        "price": round(p.predicted_price), "low": round(p.lower_bound), "high": round(p.upper_bound),
        "asked_price": p.asked_price, "verdict": p.verdict, "created_at": iso(p.created_at),
        "ram_gb": (p.input_data or {}).get("ram_gb"), "storage_gb": (p.input_data or {}).get("storage_gb"),
    }
    if full:
        out["features"] = p.input_data
        out["model_name"] = p.model_name
    return out


def phone_name_for(body_name, features):
    if body_name:
        return body_name.strip()[:160]
    brand = (features or {}).get("brand") or ""
    return f"{brand} (manual)".strip()


def prediction_fields(user_id, body, result):
    """ئەو خانانەی پێویستن بۆ پاشەکەوتکردنی پێشبینییەک."""
    v = result.get("verdict") or {}
    return {
        "user_id": user_id,
        "phone_id": body.phone_id,
        "phone_name": phone_name_for(body.phone_name, result["features"]),
        "brand": result["features"].get("brand"),
        "input_data": result["features"],
        "predicted_price": float(result["price"]),
        "lower_bound": float(result["low"]),
        "upper_bound": float(result["high"]),
        "asked_price": body.asked_price,
        "verdict": v.get("status"),
        "model_name": result.get("model"),
    }


def dashboard(preds, model_meta, admin=None, days=14, now=None):
    """preds: لیستی پێشبینییەکانی بەکارهێنەر (ORM یان هاوشێوە)."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date()
    start = today - timedelta(days=days - 1)
    per_day = Counter()
    for p in preds:
        d = p.created_at.date()
        if d >= start:
            per_day[d] += 1
    series = [{"date": (start + timedelta(days=i)).isoformat(),
               "count": per_day.get(start + timedelta(days=i), 0)} for i in range(days)]
    brands = Counter(p.brand or "?" for p in preds)
    total = len(preds)
    verdicts = Counter(p.verdict for p in preds if p.verdict)
    recent = sorted(preds, key=lambda p: p.created_at, reverse=True)[:5]
    best = next((r for r in model_meta.get("results", []) if r["name"] == model_meta.get("best_model")), None)
    return {
        "total": total,
        "avg_price": round(sum(p.predicted_price for p in preds) / total) if total else None,
        "today": per_day.get(today, 0),
        "series": series,
        "brands": [{"brand": b, "count": c, "pct": round(c / total * 100, 1)} for b, c in brands.most_common(5)],
        "verdicts": {k: verdicts.get(k, 0) for k in ("cheap", "fair", "expensive")},
        "recent": [prediction_out(p) for p in recent],
        "model": {"name": model_meta.get("best_model"),
                  "r2": best["test"]["r2"] if best else None,
                  "mae": best["test"]["mae"] if best else None,
                  "is_sample_data": model_meta.get("is_sample_data", False)},
        "admin": admin,
    }
