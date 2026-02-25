"""
Branches API Router.

Provides CRUD operations for restaurant branches.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from pymongo import ReturnDocument

from .. import database
from ..utils.serializers import serialize_all
from ..redis_manager import redis_manager, CACHE_BRANCHES, TTL_BRANCHES

router = APIRouter(prefix="/api/branches", tags=["branches"])

DEFAULT_SCHEDULE = [
    {"day": "monday", "enabled": True, "open_time": "08:00", "close_time": "22:00"},
    {"day": "tuesday", "enabled": True, "open_time": "08:00", "close_time": "22:00"},
    {"day": "wednesday", "enabled": True, "open_time": "08:00", "close_time": "22:00"},
    {"day": "thursday", "enabled": True, "open_time": "08:00", "close_time": "22:00"},
    {"day": "friday", "enabled": True, "open_time": "08:00", "close_time": "22:00"},
    {"day": "saturday", "enabled": True, "open_time": "08:00", "close_time": "22:00"},
    {"day": "sunday", "enabled": True, "open_time": "08:00", "close_time": "22:00"},
]


@router.get("/")
async def list_branches():
    """List all branches."""
    cached = await redis_manager.get_cached(CACHE_BRANCHES)
    if cached is not None:
        return cached

    if not database.connected or database.branches is None:
        return []

    branches = list(database.branches.find().sort("name", 1))
    result = [serialize_all(b) for b in branches]

    await redis_manager.set_cached(CACHE_BRANCHES, result, TTL_BRANCHES)
    return result


@router.get("/{branch_id}")
async def get_branch(branch_id: str):
    """Get a single branch by ID."""
    if not database.connected or database.branches is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(branch_id):
        raise HTTPException(status_code=400, detail="Invalid branch ID")

    branch = database.branches.find_one({"_id": ObjectId(branch_id)})
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    return serialize_all(branch)


@router.post("/")
async def create_branch(data: dict):
    """Create a new branch."""
    if not database.connected or database.branches is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not data.get("name", "").strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if not data.get("base_domain", "").strip():
        raise HTTPException(status_code=400, detail="Base domain is required")
    if not data.get("timezone", "").strip():
        raise HTTPException(status_code=400, detail="Timezone is required")

    if not data.get("schedule"):
        data["schedule"] = DEFAULT_SCHEDULE

    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()

    # Remove _id if present (for create)
    data.pop("_id", None)

    result = database.branches.insert_one(data)
    data["_id"] = result.inserted_id

    await redis_manager.invalidate_key(CACHE_BRANCHES)
    return serialize_all(data)


@router.put("/{branch_id}")
async def update_branch(branch_id: str, data: dict):
    """Update an existing branch."""
    if not database.connected or database.branches is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(branch_id):
        raise HTTPException(status_code=400, detail="Invalid branch ID")

    existing = database.branches.find_one({"_id": ObjectId(branch_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Branch not found")

    data["updated_at"] = datetime.utcnow()
    # Don't overwrite _id or created_at
    data.pop("_id", None)
    data.pop("created_at", None)

    updated = database.branches.find_one_and_update(
        {"_id": ObjectId(branch_id)},
        {"$set": data},
        return_document=ReturnDocument.AFTER
    )

    await redis_manager.invalidate_key(CACHE_BRANCHES)
    return serialize_all(updated)


@router.delete("/{branch_id}")
async def delete_branch(branch_id: str):
    """Delete a branch."""
    if not database.connected or database.branches is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(branch_id):
        raise HTTPException(status_code=400, detail="Invalid branch ID")

    result = database.branches.delete_one({"_id": ObjectId(branch_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Branch not found")

    await redis_manager.invalidate_key(CACHE_BRANCHES)
    return {"status": "deleted", "branch_id": branch_id}
