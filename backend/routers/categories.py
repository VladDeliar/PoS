from fastapi import APIRouter, HTTPException
from bson import ObjectId

from .. import database
from ..models import CategoryCreate
from ..utils.serializers import serialize_doc
from ..utils.data_fetchers import get_categories_list
from ..redis_manager import redis_manager, CACHE_CATEGORIES, TTL_CATEGORIES

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/")
async def get_categories():
    # Try cache first
    cached = await redis_manager.get_cached(CACHE_CATEGORIES)
    if cached is not None:
        return cached

    # Get from database
    result = get_categories_list()

    # Cache the result
    await redis_manager.set_cached(CACHE_CATEGORIES, result, TTL_CATEGORIES)
    return result


@router.post("/")
async def create_category(data: CategoryCreate):
    if not database.connected or database.categories is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = database.categories.insert_one(data.model_dump())

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_CATEGORIES)

    return {"_id": str(result.inserted_id), **data.model_dump()}


@router.delete("/{category_id}")
async def delete_category(category_id: str):
    if not database.connected or database.categories is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = database.categories.delete_one({"_id": ObjectId(category_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_CATEGORIES)

    return {"status": "deleted"}
