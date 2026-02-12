from fastapi import APIRouter, HTTPException
from bson import ObjectId

from .. import database
from ..models import ModifierGroupCreate
from ..utils.serializers import serialize_doc, serialize_docs
from ..utils.demo_data import DEMO_MODIFIERS
from ..redis_manager import redis_manager, CACHE_MODIFIERS, TTL_MODIFIERS

router = APIRouter(prefix="/api/modifiers", tags=["modifiers"])


@router.get("/")
async def get_modifiers():
    """Get all modifier groups"""
    # Try cache first
    cached = await redis_manager.get_cached(CACHE_MODIFIERS)
    if cached is not None:
        return cached

    if not database.connected or database.modifiers is None:
        return DEMO_MODIFIERS

    modifiers = list(database.modifiers.find())
    result = serialize_docs(modifiers)

    # Cache the result
    await redis_manager.set_cached(CACHE_MODIFIERS, result, TTL_MODIFIERS)

    return result


@router.post("/")
async def create_modifier(data: ModifierGroupCreate):
    """Create a new modifier group"""
    if not database.connected or database.modifiers is None:
        modifier_doc = data.model_dump()
        modifier_doc["_id"] = str(len(DEMO_MODIFIERS) + 1)
        DEMO_MODIFIERS.append(modifier_doc)
        return modifier_doc

    modifier_doc = data.model_dump()
    result = database.modifiers.insert_one(modifier_doc)
    modifier_doc["_id"] = str(result.inserted_id)

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_MODIFIERS)

    return modifier_doc


@router.put("/{modifier_id}")
async def update_modifier(modifier_id: str, data: ModifierGroupCreate):
    """Update a modifier group"""
    if not database.connected or database.modifiers is None:
        for mod in DEMO_MODIFIERS:
            if mod["_id"] == modifier_id:
                mod.update(data.model_dump())
                return mod
        raise HTTPException(status_code=404, detail="Modifier not found")

    result = database.modifiers.update_one(
        {"_id": ObjectId(modifier_id)},
        {"$set": data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Modifier not found")

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_MODIFIERS)

    return {"status": "updated"}


@router.delete("/{modifier_id}")
async def delete_modifier(modifier_id: str):
    """Delete a modifier group"""
    if not database.connected or database.modifiers is None:
        DEMO_MODIFIERS[:] = [m for m in DEMO_MODIFIERS if m["_id"] != modifier_id]
        return {"status": "deleted"}

    result = database.modifiers.delete_one({"_id": ObjectId(modifier_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Modifier not found")

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_MODIFIERS)

    return {"status": "deleted"}


@router.put("/{modifier_id}/toggle")
async def toggle_modifier(modifier_id: str, data: dict):
    """Toggle modifier enabled/disabled status"""
    if not database.connected or database.modifiers is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    is_enabled = data.get("is_enabled", True)
    result = database.modifiers.update_one(
        {"_id": ObjectId(modifier_id)},
        {"$set": {"is_enabled": is_enabled}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Modifier not found")

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_MODIFIERS)

    return {"status": "toggled", "is_enabled": is_enabled}


@router.post("/{modifier_id}/copy")
async def copy_modifier(modifier_id: str):
    """Copy a modifier group with a new ID"""
    if not database.connected or database.modifiers is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    modifier = database.modifiers.find_one({"_id": ObjectId(modifier_id)})
    if not modifier:
        raise HTTPException(status_code=404, detail="Modifier not found")

    del modifier["_id"]
    modifier["name"] = f"{modifier['name']} (копія)"

    result = database.modifiers.insert_one(modifier)
    modifier["_id"] = str(result.inserted_id)

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_MODIFIERS)

    return serialize_doc(modifier)
