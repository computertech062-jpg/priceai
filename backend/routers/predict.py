from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import api_error, get_optional_user, get_predictor, require_login
from ..ml.predictor import FeatureError, SpecConflict, VariantError
from ..models import Prediction, User
from ..schemas import CompareIn, PredictIn
from ..services import phone_name_for, prediction_fields

router = APIRouter(prefix="/api", tags=["Prediction"], dependencies=[Depends(require_login)])


def require_phone(predictor, phone_id, **extra):
    """پێشبینی تەنها بۆ مۆبایلێکی ڕاستەقینەی ناو کاتالۆگ: تایبەتمەندییەکان لە داتاکەوە دێن."""
    if not phone_id:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "phone_required", **extra)
    if phone_id not in predictor.catalog.by_id:
        raise api_error(status.HTTP_404_NOT_FOUND, "phone_not_found", **extra)


@router.post("/predict")
def predict(body: PredictIn, db: Session = Depends(get_db),
            user: User | None = Depends(get_optional_user), predictor=Depends(get_predictor)):
    """
    پێشبینیی نرخ. بەبێ چوونەژوورەوەش کار دەکات.
    ئەگەر بەکارهێنەر چووبێتە ژوورەوە و save=true بێت، لە مێژوودا پاشەکەوت دەکرێت.
    """
    require_phone(predictor, body.phone_id)
    try:
        result = predictor.predict(body.features, asked_price=body.asked_price,
                                   with_explanation=body.explain, with_similar=body.similar,
                                   exclude_id=body.phone_id, phone_id=body.phone_id)
    except SpecConflict as e:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "spec_conflict", field=e.field)
    except FeatureError as e:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_feature", field=e.field)
    except VariantError as e:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_variant", ram=e.ram, storage=e.storage)

    result["prediction_id"] = None
    if user and body.save:
        record = Prediction(**prediction_fields(user.id, body, result))
        db.add(record)
        db.commit()
        result["prediction_id"] = record.id
    return result


@router.post("/compare")
def compare(body: CompareIn, predictor=Depends(get_predictor)):
    items = []
    for i, item in enumerate(body.items):
        require_phone(predictor, item.phone_id, index=i)
        try:
            r = predictor.predict(item.features, asked_price=item.asked_price,
                                  with_explanation=True, with_similar=False, phone_id=item.phone_id)
        except SpecConflict as e:
            raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "spec_conflict", field=e.field, index=i)
        except FeatureError as e:
            raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_feature", field=e.field, index=i)
        except VariantError as e:
            raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_variant", index=i,
                            ram=e.ram, storage=e.storage)
        r["phone_id"] = item.phone_id
        r["phone_name"] = phone_name_for(item.phone_name, r["features"])
        r["explanation"]["items"] = r["explanation"]["items"][:5]
        items.append(r)
    # باشترین بەها: ئەگەر نرخی داواکراو هەبێت، ئەوەی زۆرترین داشکاندنی هەیە بەرامبەر نرخی گونجاو
    def value_score(r):
        v = r.get("verdict")
        return -v["diff_pct"] if v else None

    scores = [value_score(r) for r in items]
    best = None
    if all(s is not None for s in scores):
        best = max(range(len(items)), key=lambda i: scores[i])
    return {"items": items, "best_value_index": best}
