from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from pymongo import UpdateOne

from .. import database
from ..models import MenuItemCreate
from ..utils.data_fetchers import get_menu_items_list
from ..utils.demo_data import DEMO_MENU_ITEMS

router = APIRouter(prefix="/api/menu-items", tags=["menu"])


@router.get("/")
async def get_menu_items(active_only: bool = True):
    """Get menu items with product data"""
    return get_menu_items_list(active_only)


@router.post("/")
async def add_to_menu(data: MenuItemCreate):
    """Add a product or combo to the menu"""
    if not database.connected or database.menu_items is None:
        menu_item = data.model_dump()
        menu_item["_id"] = str(len(DEMO_MENU_ITEMS) + 1)
        menu_item["created_at"] = datetime.utcnow().isoformat()
        DEMO_MENU_ITEMS.append(menu_item)
        return menu_item

    item_type = data.item_type or "product"

    if item_type == "combo":
        if not data.combo_id:
            raise HTTPException(status_code=400, detail="combo_id is required for combos")
        combo = database.combos.find_one({"_id": ObjectId(data.combo_id)})
        if not combo:
            raise HTTPException(status_code=404, detail="Комбо не знайдено")

        existing = database.menu_items.find_one({"combo_id": data.combo_id, "item_type": "combo"})
        if existing:
            raise HTTPException(status_code=400, detail="Комбо вже є в меню")
    else:
        if not data.product_id:
            raise HTTPException(status_code=400, detail="product_id is required for products")
        product = database.products.find_one({"_id": ObjectId(data.product_id)})
        if not product:
            raise HTTPException(status_code=404, detail="Продукт не знайдено")

        existing = database.menu_items.find_one({"product_id": data.product_id})
        if existing:
            raise HTTPException(status_code=400, detail="Продукт вже є в меню")

    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    result = database.menu_items.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


@router.put("/{menu_item_id}")
async def update_menu_item(menu_item_id: str, data: MenuItemCreate):
    """Update a menu item"""
    if not database.connected or database.menu_items is None:
        for item in DEMO_MENU_ITEMS:
            if item["_id"] == menu_item_id:
                item.update(data.model_dump())
                return item
        raise HTTPException(status_code=404, detail="Позицію меню не знайдено")

    result = database.menu_items.update_one(
        {"_id": ObjectId(menu_item_id)},
        {"$set": data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Позицію меню не знайдено")
    return {"status": "updated"}


@router.delete("/{menu_item_id}")
async def remove_from_menu(menu_item_id: str):
    """Remove a product from the menu"""
    if not database.connected or database.menu_items is None:
        DEMO_MENU_ITEMS[:] = [m for m in DEMO_MENU_ITEMS if m["_id"] != menu_item_id]
        return {"status": "deleted"}

    result = database.menu_items.delete_one({"_id": ObjectId(menu_item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Позицію меню не знайдено")
    return {"status": "deleted"}


@router.post("/batch")
async def batch_add_to_menu(product_ids: List[str]):
    """Add multiple products to menu at once"""
    if not database.connected or database.menu_items is None:
        added = []
        for pid in product_ids:
            if not any(m.get("product_id") == pid for m in DEMO_MENU_ITEMS):
                item = {"_id": str(len(DEMO_MENU_ITEMS) + 1), "item_type": "product", "product_id": pid, "is_active": True, "sort_order": 0}
                DEMO_MENU_ITEMS.append(item)
                added.append(item["_id"])
        return {"added": added}

    added = []
    for product_id in product_ids:
        existing = database.menu_items.find_one({"product_id": product_id})
        if not existing:
            doc = {
                "item_type": "product",
                "product_id": product_id,
                "is_active": True,
                "sort_order": 0,
                "created_at": datetime.utcnow()
            }
            result = database.menu_items.insert_one(doc)
            added.append(str(result.inserted_id))
    return {"added": added}


@router.post("/reorder")
async def reorder_menu_items(req: Request):
    """Update sort order for multiple menu items"""
    try:
        items = await req.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    if not database.connected or database.menu_items is None:
        for update in items:
            for item in DEMO_MENU_ITEMS:
                if item["_id"] == update["_id"]:
                    item["sort_order"] = update["sort_order"]
        return {"status": "updated"}

    operations = [
        UpdateOne(
            {"_id": ObjectId(update["_id"])},
            {"$set": {"sort_order": update["sort_order"]}}
        )
        for update in items
    ]
    if operations:
        database.menu_items.bulk_write(operations, ordered=False)
    return {"status": "updated"}
