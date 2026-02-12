from datetime import datetime

from fastapi import APIRouter, HTTPException
from bson import ObjectId

from .. import database
from ..models import ComboCreate
from ..utils.serializers import serialize_docs
from ..utils.demo_data import DEMO_COMBOS, DEMO_MENU_ITEMS

router = APIRouter(prefix="/api/combos", tags=["combos"])


@router.get("/")
async def get_combos(available: bool = None, skip: int = 0, limit: int = 100):
    """Get all combos with pagination"""
    if not database.connected or database.combos is None:
        result = DEMO_COMBOS
        if available is not None:
            result = [c for c in result if c.get("available") == available]
        return {"items": result[skip:skip + limit], "total": len(result), "skip": skip, "limit": limit}

    query = {}
    if available is not None:
        query["available"] = available

    total = database.combos.count_documents(query)
    combos = list(database.combos.find(query).skip(skip).limit(limit))

    return {
        "items": serialize_docs(combos),
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/")
async def create_combo(data: ComboCreate):
    """Create a new combo"""
    if not database.connected or database.combos is None:
        combo_doc = data.model_dump()
        combo_doc["_id"] = str(len(DEMO_COMBOS) + 1)
        combo_doc["created_at"] = datetime.utcnow().isoformat()
        DEMO_COMBOS.append(combo_doc)
        return combo_doc

    combo_doc = data.model_dump()
    combo_doc["created_at"] = datetime.utcnow()
    result = database.combos.insert_one(combo_doc)
    combo_doc["_id"] = str(result.inserted_id)
    combo_doc["created_at"] = combo_doc["created_at"].isoformat()
    return combo_doc


@router.put("/{combo_id}")
async def update_combo(combo_id: str, data: ComboCreate):
    """Update a combo"""
    if not database.connected or database.combos is None:
        for combo in DEMO_COMBOS:
            if combo["_id"] == combo_id:
                combo.update(data.model_dump())
                return combo
        raise HTTPException(status_code=404, detail="Combo not found")

    result = database.combos.update_one(
        {"_id": ObjectId(combo_id)},
        {"$set": data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Combo not found")
    return {"status": "updated"}


@router.delete("/{combo_id}")
async def delete_combo(combo_id: str):
    """Delete a combo"""
    if not database.connected or database.combos is None:
        DEMO_COMBOS[:] = [c for c in DEMO_COMBOS if c["_id"] != combo_id]
        return {"status": "deleted"}

    result = database.combos.delete_one({"_id": ObjectId(combo_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Combo not found")
    return {"status": "deleted"}


@router.get("/available-for-menu")
async def get_combos_available_for_menu():
    """Get combos that are not yet added to the menu"""
    if not database.connected or database.combos is None:
        menu_combo_ids = [
            item.get("combo_id")
            for item in DEMO_MENU_ITEMS
            if item.get("item_type") == "combo"
        ]
        return [c for c in DEMO_COMBOS if c["_id"] not in menu_combo_ids and c.get("available", True)]

    menu_combo_ids = [
        item["combo_id"]
        for item in database.menu_items.find({"item_type": "combo"})
        if item.get("combo_id")
    ]

    query = {"available": True}
    if menu_combo_ids:
        query["_id"] = {"$nin": [ObjectId(cid) for cid in menu_combo_ids]}

    return serialize_docs(database.combos.find(query))
