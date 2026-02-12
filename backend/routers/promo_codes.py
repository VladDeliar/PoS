from datetime import datetime

from fastapi import APIRouter, HTTPException
from bson import ObjectId

from .. import database
from ..models import PromoCodeCreate
from ..utils.serializers import serialize_docs
from ..utils.promo import validate_promo_code, calculate_discount
from ..utils.demo_data import DEMO_PROMO_CODES

router = APIRouter(prefix="/api/promo-codes", tags=["promo-codes"])


@router.get("/")
async def get_promo_codes(skip: int = 0, limit: int = 100):
    """Get all promo codes (admin) with pagination"""
    if not database.connected or database.promo_codes is None:
        return {
            "items": DEMO_PROMO_CODES[skip:skip + limit],
            "total": len(DEMO_PROMO_CODES),
            "skip": skip,
            "limit": limit
        }

    total = database.promo_codes.count_documents({})
    promo_codes = list(database.promo_codes.find().sort("created_at", -1).skip(skip).limit(limit))

    return {
        "items": serialize_docs(promo_codes),
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/")
async def create_promo_code(data: PromoCodeCreate):
    """Create a new promo code"""
    if not database.connected or database.promo_codes is None:
        promo_doc = data.model_dump()
        promo_doc["_id"] = str(len(DEMO_PROMO_CODES) + 1)
        promo_doc["code"] = promo_doc["code"].upper()
        promo_doc["usage_count"] = 0
        promo_doc["created_at"] = datetime.utcnow().isoformat()
        DEMO_PROMO_CODES.append(promo_doc)
        return promo_doc

    existing = database.promo_codes.find_one({"code": data.code.upper()})
    if existing:
        raise HTTPException(status_code=400, detail="Промокод вже існує")

    promo_doc = data.model_dump()
    promo_doc["code"] = promo_doc["code"].upper()
    promo_doc["usage_count"] = 0
    promo_doc["created_at"] = datetime.utcnow()

    result = database.promo_codes.insert_one(promo_doc)
    promo_doc["_id"] = str(result.inserted_id)
    promo_doc["created_at"] = promo_doc["created_at"].isoformat()
    return promo_doc


@router.put("/{promo_id}")
async def update_promo_code(promo_id: str, data: PromoCodeCreate):
    """Update a promo code"""
    if not database.connected or database.promo_codes is None:
        for promo in DEMO_PROMO_CODES:
            if promo["_id"] == promo_id:
                promo.update(data.model_dump())
                promo["code"] = promo["code"].upper()
                return promo
        raise HTTPException(status_code=404, detail="Промокод не знайдено")

    update_data = data.model_dump()
    update_data["code"] = update_data["code"].upper()

    result = database.promo_codes.update_one(
        {"_id": ObjectId(promo_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Промокод не знайдено")
    return {"status": "updated"}


@router.delete("/{promo_id}")
async def delete_promo_code(promo_id: str):
    """Delete a promo code"""
    if not database.connected or database.promo_codes is None:
        DEMO_PROMO_CODES[:] = [p for p in DEMO_PROMO_CODES if p["_id"] != promo_id]
        return {"status": "deleted"}

    result = database.promo_codes.delete_one({"_id": ObjectId(promo_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Промокод не знайдено")
    return {"status": "deleted"}


@router.post("/validate")
async def validate_promo(code: str, order_total: float = 0):
    """Validate a promo code for an order"""
    result = validate_promo_code(code, order_total)
    if result["valid"]:
        promo = result["promo"]
        discount = calculate_discount(promo, order_total)
        return {
            "valid": True,
            "code": promo["code"],
            "discount_type": promo["discount_type"],
            "discount_value": promo["discount_value"],
            "discount_amount": discount,
            "new_total": order_total - discount
        }
    return result
