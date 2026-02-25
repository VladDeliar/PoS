import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from .. import database
from ..models import CustomerCreate
from ..utils.serializers import serialize_doc, serialize_docs

router = APIRouter(prefix="/api/customers", tags=["customers"])


def normalize_phone(phone: str) -> str:
    """Normalize phone number: strip spaces, dashes, parentheses"""
    return re.sub(r'[\s\-\(\)]', '', phone.strip())


@router.get("/")
async def get_customers(
    search: str = "",
    category_id: str = "",
    skip: int = 0,
    limit: int = 50
):
    """Get customers list with search and filter"""
    if not database.connected or database.customers is None:
        return {"items": [], "total": 0, "skip": skip, "limit": limit}

    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]
    if category_id:
        query["category_ids"] = category_id

    total = database.customers.count_documents(query)
    customers = list(
        database.customers.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    return {
        "items": serialize_docs(customers),
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/lookup/{phone}")
async def lookup_customer(phone: str):
    """Lookup customer by phone for checkout discount"""
    if not database.connected or database.customers is None:
        return {"found": False}

    phone_normalized = normalize_phone(phone)
    if not phone_normalized:
        return {"found": False}

    customer = database.customers.find_one({"phone": phone_normalized})
    if not customer:
        return {"found": False, "phone": phone_normalized}

    # Get categories and find highest discount
    discount_percent = 0
    discount_label = ""
    category_names = []

    if customer.get("category_ids"):
        cat_ids = []
        for cid in customer["category_ids"]:
            if ObjectId.is_valid(cid):
                cat_ids.append(ObjectId(cid))

        if cat_ids:
            categories = list(database.customer_categories.find({
                "_id": {"$in": cat_ids},
                "is_active": True
            }))
            for cat in categories:
                category_names.append(cat["name"])
                if cat.get("discount_percent", 0) > discount_percent:
                    discount_percent = cat["discount_percent"]
                    discount_label = f"Знижка для категорії '{cat['name']}': -{cat['discount_percent']}%"

    return {
        "found": True,
        "customer_name": customer.get("name", ""),
        "phone": customer.get("phone", ""),
        "category_names": category_names,
        "discount_percent": discount_percent,
        "discount_label": discount_label,
        "order_count": customer.get("order_count", 0),
        "total_spent": customer.get("total_spent", 0)
    }


@router.get("/{customer_id}")
async def get_customer(customer_id: str):
    """Get a single customer with order history"""
    if not database.connected or database.customers is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        customer = database.customers.find_one({"_id": ObjectId(customer_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Невірний ID")

    if not customer:
        raise HTTPException(status_code=404, detail="Клієнта не знайдено")

    result = serialize_doc(customer)

    # Fetch recent orders
    if customer.get("order_history"):
        order_ids = [ObjectId(oid) for oid in customer["order_history"][-20:] if ObjectId.is_valid(oid)]
        if order_ids:
            orders = list(database.orders.find(
                {"_id": {"$in": order_ids}}
            ).sort("created_at", -1))
            result["orders"] = serialize_docs(orders)
        else:
            result["orders"] = []
    else:
        result["orders"] = []

    # Fetch category details
    if customer.get("category_ids"):
        cat_ids = [ObjectId(cid) for cid in customer["category_ids"] if ObjectId.is_valid(cid)]
        if cat_ids:
            cats = list(database.customer_categories.find({"_id": {"$in": cat_ids}}))
            result["categories"] = serialize_docs(cats)
        else:
            result["categories"] = []
    else:
        result["categories"] = []

    return result


@router.post("/")
async def create_customer(data: CustomerCreate):
    """Create a new customer (admin)"""
    if not database.connected or database.customers is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    phone = normalize_phone(data.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Телефон обов'язковий")

    existing = database.customers.find_one({"phone": phone})
    if existing:
        raise HTTPException(status_code=400, detail="Клієнт з таким телефоном вже існує")

    doc = {
        "name": data.name.strip(),
        "phone": phone,
        "category_ids": data.category_ids,
        "notes": data.notes,
        "order_history": [],
        "order_count": 0,
        "total_spent": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = database.customers.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    return doc


@router.put("/{customer_id}")
async def update_customer(customer_id: str, data: CustomerCreate):
    """Update customer info (categories, notes, name)"""
    if not database.connected or database.customers is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    phone = normalize_phone(data.phone)

    # Check if phone is taken by another customer
    existing = database.customers.find_one({"phone": phone, "_id": {"$ne": ObjectId(customer_id)}})
    if existing:
        raise HTTPException(status_code=400, detail="Цей телефон вже належить іншому клієнту")

    update_data = {
        "name": data.name.strip(),
        "phone": phone,
        "category_ids": data.category_ids,
        "notes": data.notes,
        "updated_at": datetime.utcnow()
    }

    result = database.customers.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Клієнта не знайдено")
    return {"status": "updated"}


@router.delete("/{customer_id}")
async def delete_customer(customer_id: str):
    """Delete a customer"""
    if not database.connected or database.customers is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    result = database.customers.delete_one({"_id": ObjectId(customer_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Клієнта не знайдено")
    return {"status": "deleted"}
