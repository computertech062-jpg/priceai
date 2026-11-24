from datetime import date

from fastapi import APIRouter, Depends, Query, status

from ..deps import api_error, get_forecaster, get_predictor, get_price_history, require_login

router = APIRouter(prefix="/api", tags=["Phones"], dependencies=[Depends(require_login)])


@router.get("/features")
def features(predictor=Depends(get_predictor)):
    """پێناسەی تایبەتمەندییەکان، Frontend فۆرمەکەی لێرەوە دروست دەکات."""
    return predictor.schema()


@router.get("/phones/search")
def search(q: str = Query("", max_length=80), limit: int = Query(8, ge=1, le=20),
           predictor=Depends(get_predictor)):
    return {"results": predictor.catalog.search(q, limit=limit)}


@router.get("/phones/brands")
def brands(predictor=Depends(get_predictor)):
    return {"brands": predictor.catalog.brands()}


@router.get("/phones/{phone_id}")
def phone(phone_id: str, predictor=Depends(get_predictor)):
    p = predictor.catalog.get(phone_id)
    if not p:
        raise api_error(status.HTTP_404_NOT_FOUND, "phone_not_found")
    return p


@router.get("/phones/{phone_id}/price-history")
def price_history(phone_id: str, ram: float | None = Query(None, gt=0), storage: float | None = Query(None, gt=0),
                  predictor=Depends(get_predictor), history=Depends(get_price_history)):
    """نرخە ڕاستەقینە کۆنەکانی ئەم مۆبایلە بە پێی کات (لە archive.org)."""
    p = predictor.catalog.by_id.get(phone_id)
    if not p:
        raise api_error(status.HTTP_404_NOT_FOUND, "phone_not_found")
    return history.series(p["model"], ram, storage)


@router.get("/phones/{phone_id}/forecast")
def forecast(phone_id: str, ram: float | None = Query(None, gt=0), storage: float | None = Query(None, gt=0),
             ai_price: float | None = Query(None, gt=0, le=20000),
             predictor=Depends(get_predictor), forecaster=Depends(get_forecaster),
             history=Depends(get_price_history)):
    """
    نرخی ئەمڕۆ و نرخ دوای ساڵێک بۆ ئەم جۆرە (RAM + بیرگە)، بە پێی مۆبایلە هاوشێوەکانی پێشوو.
    خاڵی دەستپێک نرخی بازاڕی ئەم جۆرەیە. ئەگەر نەبوو، نرخی خەمڵێنراوی AI (ai_price) بەکاردێت.
    """
    p = predictor.catalog.by_id.get(phone_id)
    if not p:
        raise api_error(status.HTTP_404_NOT_FOUND, "phone_not_found")
    v = next((v for v in p["variants"] if v.get("price_usd") and v["ram_gb"] == ram and v["storage_gb"] == storage), None)
    start, basis, when = (v["price_usd"], "market", None) if v else (ai_price, "ai", None)
    # ئەگەر archive.org نرخێکی نوێتری هەمان جۆری هەبێت (بازاڕی ناڕەسمی)، لەوێوە دەست پێدەکەین
    h = history.series(p["model"], ram, storage)
    obs = forecaster.dates.get(p["model"], {}).get("updated")
    if h.get("available") and h["exact_variant"] and h["price_type"] == "unofficial":
        last = h["points"][-1]
        last_date = date.fromisoformat(last["date"])
        if obs is None or last_date > obs:
            start, basis, when = last["price_usd"], "history", last_date
    if not start:
        return {"available": False, "reason": "no_price"}
    out = forecaster.forecast(p["model"], p["brand"], p["specs"].get("chipset_tier"), start, observed_date=when)
    if out.get("available"):
        out["basis"] = basis
        out["accuracy"] = {k: forecaster.backtest().get(k) for k in ("mape", "naive_mape", "n", "coverage_heldout_pct")}
    return out


@router.get("/forecast/backtest")
def forecast_backtest(forecaster=Depends(get_forecaster)):
    """هەڵەی پێشبینیی 12 مانگ لەسەر نرخە ڕاستەقینەکان (Backtest)."""
    return forecaster.backtest()
