from datetime import datetime

from bson import ObjectId

from .. import database
from ..utils.serializers import serialize_doc, serialize_docs
from ..utils.demo_data import DEMO_CATEGORIES, DEMO_PRODUCTS, DEMO_MENU_ITEMS


def init_default_data():
    """Initialize default data if empty"""
    _init_default_customer_categories()


def _init_default_customer_categories():
    """Initialize default customer categories if empty"""
    if not database.connected or database.customer_categories is None:
        return
    if database.customer_categories.count_documents({}) == 0:
        defaults = [
            {
                "name": "Друзі",
                "discount_percent": 15,
                "color": "#FF9800",
                "description": "Знижка для друзів закладу",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Постійні",
                "discount_percent": 10,
                "color": "#4CAF50",
                "description": "Знижка для постійних клієнтів",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ]
        database.customer_categories.insert_many(defaults)
        print("Default customer categories created")


def get_categories_list():
    """Get categories from DB or demo data"""
    if database.connected and database.categories is not None:
        return serialize_docs(database.categories.find().sort("sort_order", 1))
    return DEMO_CATEGORIES


def get_products_list(available_only=False):
    """Get products from DB or demo data"""
    if database.connected and database.products is not None:
        query = {"available": True} if available_only else {}
        return serialize_docs(database.products.find(query))
    if available_only:
        return [p for p in DEMO_PRODUCTS if p.get("available", True)]
    return DEMO_PRODUCTS


def get_menu_items_list(active_only=True):
    """Get menu items with product/combo data (for POS/customer menu)"""
    if not database.connected or database.menu_items is None:
        if DEMO_MENU_ITEMS:
            return DEMO_MENU_ITEMS
        return get_products_list(available_only=active_only)

    match_query = {"is_active": True} if active_only else {}

    # Optimized: single aggregation with $lookup instead of 3 separate queries
    pipeline = [
        {"$match": match_query},
        {"$sort": {"sort_order": 1}},
        # Convert string IDs to ObjectId for lookup
        {"$addFields": {
            "product_oid": {
                "$cond": {
                    "if": {"$and": [
                        {"$eq": [{"$ifNull": ["$item_type", "product"]}, "product"]},
                        {"$ne": ["$product_id", None]}
                    ]},
                    "then": {"$toObjectId": "$product_id"},
                    "else": None
                }
            },
            "combo_oid": {
                "$cond": {
                    "if": {"$and": [
                        {"$eq": ["$item_type", "combo"]},
                        {"$ne": ["$combo_id", None]}
                    ]},
                    "then": {"$toObjectId": "$combo_id"},
                    "else": None
                }
            }
        }},
        # Lookup products
        {"$lookup": {
            "from": "products",
            "localField": "product_oid",
            "foreignField": "_id",
            "as": "product_data"
        }},
        # Lookup combos
        {"$lookup": {
            "from": "combos",
            "localField": "combo_oid",
            "foreignField": "_id",
            "as": "combo_data"
        }},
        # Extract first element from arrays
        {"$addFields": {
            "product": {"$arrayElemAt": ["$product_data", 0]},
            "combo": {"$arrayElemAt": ["$combo_data", 0]}
        }},
        # Remove temp fields
        {"$project": {
            "product_data": 0,
            "combo_data": 0,
            "product_oid": 0,
            "combo_oid": 0
        }}
    ]

    menu_items = list(database.menu_items.aggregate(pipeline))

    result = []
    for item in menu_items:
        item_type = item.get("item_type", "product")

        if item_type == "combo":
            combo = item.get("combo")
            if not combo:
                continue

            merged = serialize_doc(combo)
            merged["menu_item_id"] = str(item["_id"])
            merged["is_active"] = item.get("is_active", True)
            merged["sort_order"] = item.get("sort_order", 0)
            merged["item_type"] = "combo"
            merged["price"] = combo.get("combo_price", 0)
            merged["savings"] = combo.get("regular_price", 0) - combo.get("combo_price", 0)
            if item.get("category_id"):
                merged["category_id"] = item["category_id"]
            result.append(merged)
        else:
            product = item.get("product")
            if not product:
                continue

            merged = serialize_doc(product)
            merged["menu_item_id"] = str(item["_id"])
            merged["is_active"] = item.get("is_active", True)
            merged["sort_order"] = item.get("sort_order", 0)
            merged["item_type"] = "product"
            if item.get("category_id"):
                merged["category_id"] = item["category_id"]
            result.append(merged)

    return result
