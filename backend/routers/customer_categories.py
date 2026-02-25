from datetime import datetime

from fastapi import APIRouter, HTTPException
from bson import ObjectId

from .. import database
from ..models import CustomerCategoryCreate
from ..utils.serializers import serialize_doc, serialize_docs

router = APIRouter(prefix="/api/customer-categories", tags=["customer-categories"])


@router.get("/")
async def get_customer_categories():
    """Get all customer categories"""
    if not database.connected or database.customer_categories is None:
        return {"items": [], "total": 0}

    cats = list(database.customer_categories.find().sort("created_at", -1))
    return {
        "items": serialize_docs(cats),
        "total": len(cats)
    }


@router.post("/")
async def create_customer_category(data: CustomerCategoryCreate):
    """Create a new customer category"""
    if not database.connected or database.customer_categories is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()

    result = database.customer_categories.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


@router.put("/{category_id}")
async def update_customer_category(category_id: str, data: CustomerCategoryCreate):
    """Update a customer category"""
    if not database.connected or database.customer_categories is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    update_data = data.model_dump()
    result = database.customer_categories.update_one(
        {"_id": ObjectId(category_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")
    return {"status": "updated"}


@router.delete("/{category_id}")
async def delete_customer_category(category_id: str):
    """Delete a customer category"""
    if not database.connected or database.customer_categories is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Remove category from all customers that have it
    if database.customers is not None:
        database.customers.update_many(
            {"category_ids": category_id},
            {"$pull": {"category_ids": category_id}}
        )

    result = database.customer_categories.delete_one({"_id": ObjectId(category_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")
    return {"status": "deleted"}
