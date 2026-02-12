import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from pymongo import ReturnDocument

logger = logging.getLogger(__name__)

from .. import database
from ..models import OrderCreate
from ..redis_manager import redis_manager
from ..config import CHANNEL_ORDERS_NEW, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from ..telegram_bot import send_order_notification
from ..dependencies import runtime_settings
from ..utils.serializers import serialize_doc, serialize_docs
from ..utils.order_helpers import generate_order_number
from ..utils.promo import validate_promo_code, calculate_discount
from ..utils.demo_data import DEMO_ORDERS

router = APIRouter(prefix="/api", tags=["orders"])


@router.get("/orders")
async def get_orders(status: str = None):
    if not database.connected or database.orders is None:
        result = DEMO_ORDERS
        if status:
            result = [o for o in result if o["status"] == status]
        return result

    query = {}
    if status:
        query["status"] = status

    orders = list(database.orders.find(query).sort("created_at", -1))

    return serialize_docs(orders)


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get a single order by ID for tracking page"""
    if not database.connected or database.orders is None:
        for order in DEMO_ORDERS:
            if order["_id"] == order_id:
                return order
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")

    try:
        order = database.orders.find_one({"_id": ObjectId(order_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Невірний ID замовлення")

    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")

    return serialize_doc(order)


@router.post("/orders")
async def create_order(data: OrderCreate):
    # Validate items
    if not data.items:
        raise HTTPException(status_code=400, detail="Замовлення не містить товарів")

    for item in data.items:
        if item.qty <= 0:
            raise HTTPException(status_code=400, detail=f"Невірна кількість для товару: {item.name}")
        if item.price < 0:
            raise HTTPException(status_code=400, detail=f"Невірна ціна для товару: {item.name}")

    # Validate products exist and are available
    if database.connected and database.products is not None:
        product_ids = [
            ObjectId(item.product_id)
            for item in data.items
            if item.product_id and ObjectId.is_valid(item.product_id)
        ]

        if product_ids:
            products = {str(p["_id"]): p for p in database.products.find({"_id": {"$in": product_ids}})}

            for item in data.items:
                if item.product_id and ObjectId.is_valid(item.product_id):
                    product = products.get(item.product_id)
                    if not product:
                        raise HTTPException(status_code=400, detail=f"Товар '{item.name}' не знайдено")
                    if not product.get("available", True):
                        raise HTTPException(status_code=400, detail=f"Товар '{product.get('name', item.name)}' недоступний")

    subtotal = sum(item.price * item.qty for item in data.items)
    discount_amount = 0
    promo_code_used = None

    # Initialize delivery-related variables
    delivery_fee = 0
    delivery_zone_name = None
    delivery_address = None

    if data.order_type == "delivery":
        # Validate required delivery fields
        if not data.delivery_zone_id or not data.delivery_address:
            raise HTTPException(
                status_code=400,
                detail="Для доставки потрібно вказати адресу та зону"
            )

        # Get zone info from database
        if database.connected and database.delivery_zones is not None:
            try:
                zone = database.delivery_zones.find_one({"_id": ObjectId(data.delivery_zone_id)})
            except Exception:
                zone = None

            if not zone or not zone.get("enabled"):
                raise HTTPException(
                    status_code=400,
                    detail="Недійсна або вимкнена зона доставки"
                )

            # Check minimum order
            min_order = zone.get("min_order_amount", 0)
            if min_order > 0 and subtotal < min_order:
                raise HTTPException(
                    status_code=400,
                    detail=f"Мінімальна сума для доставки в цю зону: {min_order} грн"
                )

            # Calculate delivery fee (waive if above threshold)
            threshold = zone.get("free_delivery_threshold")
            if threshold and subtotal >= threshold:
                delivery_fee = 0
            else:
                delivery_fee = zone.get("delivery_fee", 0)

            delivery_zone_name = zone.get("name")
            delivery_address = data.delivery_address
        else:
            # Demo mode - accept as-is
            delivery_fee = data.delivery_fee
            delivery_zone_name = "Demo Zone"
            delivery_address = data.delivery_address

    if data.promo_code:
        promo_result = validate_promo_code(data.promo_code, subtotal)
        if promo_result["valid"]:
            promo = promo_result["promo"]
            discount_amount = calculate_discount(promo, subtotal)
            promo_code_used = promo["code"]

            if database.connected and database.promo_codes is not None:
                database.promo_codes.update_one(
                    {"code": promo["code"]},
                    {"$inc": {"usage_count": 1}}
                )

    total = subtotal - discount_amount + delivery_fee

    order_doc = {
        "order_number": generate_order_number(),
        "items": [item.model_dump() for item in data.items],
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "promo_code": promo_code_used,
        "delivery_fee": delivery_fee,
        "delivery_zone_id": data.delivery_zone_id,
        "delivery_zone_name": delivery_zone_name,
        "delivery_address": delivery_address,
        "total": total,
        "status": "new",
        "payment_status": "pending",
        "order_type": data.order_type,
        "table_number": data.table_number,
        "customer_name": data.customer_name,
        "customer_phone": data.customer_phone,
        "notes": data.notes,
        "created_at": datetime.utcnow().isoformat()
    }

    if not database.connected or database.orders is None:
        order_doc["_id"] = str(len(DEMO_ORDERS) + 1)
        DEMO_ORDERS.insert(0, order_doc)
    else:
        order_doc["created_at"] = datetime.utcnow()
        result = database.orders.insert_one(order_doc)
        order_doc["_id"] = str(result.inserted_id)
        order_doc["created_at"] = order_doc["created_at"].isoformat()

    try:
        await redis_manager.publish(CHANNEL_ORDERS_NEW, {
            "type": "new_order",
            "order": order_doc
        })
    except Exception as e:
        logger.error("Failed to publish new order event: %s", e)

    try:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            await send_order_notification(order_doc)
    except Exception as e:
        logger.error("Telegram notification error: %s", e)

    return order_doc


@router.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    valid_statuses = ["new", "preparing", "ready", "completed", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not database.connected or database.orders is None:
        for order in DEMO_ORDERS:
            if order["_id"] == order_id:
                order["status"] = status
                break
    else:
        result = database.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": status}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Order not found")

    try:
        await redis_manager.publish(CHANNEL_ORDERS_NEW, {
            "type": "order_updated",
            "order_id": order_id,
            "status": status
        })
    except Exception as e:
        logger.error("Failed to publish order update event: %s", e)

    return {"status": "updated"}


@router.put("/orders/{order_id}/payment")
async def update_payment_status(order_id: str, payment_status: str):
    if payment_status not in ["pending", "paid"]:
        raise HTTPException(status_code=400, detail="Invalid payment status")

    if not database.connected or database.orders is None:
        for order in DEMO_ORDERS:
            if order["_id"] == order_id:
                order["payment_status"] = payment_status
                break
    else:
        result = database.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"payment_status": payment_status}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Order not found")
    return {"status": "updated"}


@router.post("/orders/{order_id}/call-waiter")
async def call_waiter(order_id: str, phone: str = ""):
    """Customer calls for waiter assistance"""
    if not database.connected or database.orders is None:
        return {"status": "ok", "message": "Офіціант буде зараз"}

    try:
        # Optimized: single query instead of update + find
        order = database.orders.find_one_and_update(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "waiter_called": True,
                "waiter_called_at": datetime.utcnow(),
                "customer_phone": phone
            }},
            return_document=ReturnDocument.AFTER
        )

        if not order:
            raise HTTPException(status_code=404, detail="Замовлення не знайдено")

        await redis_manager.publish(CHANNEL_ORDERS_NEW, {
            "type": "waiter_called",
            "order_id": order_id,
            "phone": phone,
            "table_number": order.get("table_number")
        })

        return {"status": "ok", "message": "Офіціант буде зараз"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Production Status ============

@router.get("/production-status")
async def get_production_status(category_id: str = None):
    """Get production status for today - sold vs planned for products with daily norms"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    if not database.connected or database.products is None or database.orders is None:
        return {"products": []}

    query = {"daily_production_norm": {"$exists": True, "$ne": None, "$gt": 0}}
    if category_id:
        query["category_id"] = category_id

    products_with_norms = list(database.products.find(query))

    if not products_with_norms:
        return {"products": []}

    orders_query = {
        "created_at": {"$gte": today_start},
        "status": {"$ne": "cancelled"}
    }

    pipeline = [
        {"$match": orders_query},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "sold_qty": {"$sum": "$items.qty"}
        }}
    ]

    sold_aggregation = list(database.orders.aggregate(pipeline))
    sold_map = {item["_id"]: item["sold_qty"] for item in sold_aggregation}

    result = []
    for product in products_with_norms:
        product_id = str(product["_id"])
        norm = product.get("daily_production_norm", 0)
        sold_today = sold_map.get(product_id, 0)
        percentage = round((sold_today / norm * 100), 1) if norm > 0 else 0

        result.append({
            "_id": product_id,
            "name": product["name"],
            "category_id": product.get("category_id"),
            "sold_today": sold_today,
            "norm": norm,
            "percentage": percentage,
            "remaining": max(0, norm - sold_today)
        })

    result.sort(key=lambda x: x["percentage"], reverse=True)

    return {"products": result}
