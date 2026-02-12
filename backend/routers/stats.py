import io
import csv
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from bson import ObjectId

from .. import database
from ..utils.serializers import serialize_doc
from ..utils.demo_data import DEMO_ORDERS

router = APIRouter(prefix="/api", tags=["stats"])


def _parse_date_range(date_from: str, date_to: str, default_days: int = 7):
    """Parse date range strings into datetime objects with defaults."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            start_date = today_start - timedelta(days=default_days)
    else:
        start_date = today_start - timedelta(days=default_days)

    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            end_date = datetime.utcnow()
    else:
        end_date = datetime.utcnow()

    return today_start, start_date, end_date


@router.get("/stats")
async def get_stats(
    date_from: str = None,
    date_to: str = None,
    tags: str = None,
    alcohol: str = "all"
):
    """Get statistics with optional date range and product filters."""
    today_start, start_date, end_date = _parse_date_range(date_from, date_to)

    days_in_range = (end_date - start_date).days + 1

    if not database.connected or database.orders is None:
        today_revenue = sum(o.get("total", 0) for o in DEMO_ORDERS if o.get("status") != "cancelled")
        pending = len([o for o in DEMO_ORDERS if o["status"] in ["new", "preparing"]])
        completed = len([o for o in DEMO_ORDERS if o["status"] == "completed"])

        daily_stats = []
        for i in range(min(days_in_range, 30) - 1, -1, -1):
            day = start_date + timedelta(days=i)
            daily_stats.append({
                "date": day.strftime("%d.%m"),
                "orders_count": len(DEMO_ORDERS) if i == 0 else 0,
                "revenue": today_revenue if i == 0 else 0
            })

        return {
            "today_orders": len(DEMO_ORDERS),
            "today_revenue": today_revenue,
            "pending_orders": pending,
            "completed_orders": completed,
            "top_products": [],
            "daily_stats": daily_stats,
            "revenue_by_type": {"dine_in": today_revenue, "takeaway": 0, "delivery": 0},
            "hourly_distribution": []
        }

    today_orders = list(database.orders.find({"created_at": {"$gte": today_start}}))
    today_revenue = sum(o.get("total", 0) for o in today_orders if o.get("status") != "cancelled")

    pending = database.orders.count_documents({"status": {"$in": ["new", "preparing"]}})
    completed = database.orders.count_documents({"status": "completed", "created_at": {"$gte": today_start}})

    filtered_product_ids = None
    if tags or alcohol != "all":
        product_filter = {}
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                product_filter["tags"] = {"$in": tag_list}
        if alcohol == "alcohol":
            product_filter["is_alcohol"] = True
        elif alcohol == "non_alcohol":
            product_filter["is_alcohol"] = {"$ne": True}

        if product_filter and database.products is not None:
            filtered_products = list(database.products.find(product_filter, {"_id": 1}))
            filtered_product_ids = [str(p["_id"]) for p in filtered_products]

    pipeline_match = {"created_at": {"$gte": start_date, "$lte": end_date}, "status": {"$ne": "cancelled"}}
    pipeline = [
        {"$match": pipeline_match},
        {"$unwind": "$items"},
    ]

    if filtered_product_ids is not None:
        pipeline.append({"$match": {"items.product_id": {"$in": filtered_product_ids}}})

    pipeline.extend([
        {"$group": {
            "_id": "$items.name",
            "product_id": {"$first": "$items.product_id"},
            "count": {"$sum": "$items.qty"},
            "revenue": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}}
        }},
        {"$sort": {"revenue": -1}},
        {"$limit": 50}
    ])
    top_products = list(database.orders.aggregate(pipeline))

    type_pipeline = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}, "status": {"$ne": "cancelled"}}},
        {"$group": {"_id": "$order_type", "revenue": {"$sum": "$total"}, "count": {"$sum": 1}}}
    ]
    type_results = list(database.orders.aggregate(type_pipeline))
    revenue_by_type = {
        "dine_in": {"revenue": 0, "count": 0},
        "takeaway": {"revenue": 0, "count": 0},
        "delivery": {"revenue": 0, "count": 0}
    }
    for r in type_results:
        if r["_id"] in revenue_by_type:
            revenue_by_type[r["_id"]] = {"revenue": r["revenue"], "count": r["count"]}

    hourly_pipeline = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}, "status": {"$ne": "cancelled"}}},
        {"$project": {"hour": {"$hour": "$created_at"}, "total": 1}},
        {"$group": {"_id": "$hour", "orders": {"$sum": 1}, "revenue": {"$sum": "$total"}}},
        {"$sort": {"_id": 1}}
    ]
    hourly_results = list(database.orders.aggregate(hourly_pipeline))
    hourly_distribution = [{"hour": r["_id"], "orders": r["orders"], "revenue": r["revenue"]} for r in hourly_results]

    # Optimized: single aggregation instead of N queries
    daily_pipeline = [
        {"$match": {
            "created_at": {"$gte": start_date, "$lte": end_date},
            "status": {"$ne": "cancelled"}
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "orders_count": {"$sum": 1},
            "revenue": {"$sum": "$total"}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_results = {r["_id"]: r for r in database.orders.aggregate(daily_pipeline)}

    daily_stats = []
    for i in range(min(days_in_range, 30)):
        day = start_date + timedelta(days=i)
        day_key = day.strftime("%Y-%m-%d")
        day_data = daily_results.get(day_key, {"orders_count": 0, "revenue": 0})
        daily_stats.append({
            "date": day.strftime("%d.%m"),
            "orders_count": day_data["orders_count"],
            "revenue": day_data["revenue"]
        })

    period_orders = list(database.orders.find({
        "created_at": {"$gte": start_date, "$lte": end_date},
        "status": {"$ne": "cancelled"}
    }))
    period_revenue = sum(o.get("total", 0) for o in period_orders)

    return {
        "today_orders": len(today_orders),
        "today_revenue": today_revenue,
        "pending_orders": pending,
        "completed_orders": completed,
        "period_orders": len(period_orders),
        "period_revenue": period_revenue,
        "top_products": top_products,
        "daily_stats": daily_stats,
        "revenue_by_type": revenue_by_type,
        "hourly_distribution": hourly_distribution
    }


@router.get("/stats/by-tag")
async def get_stats_by_tag(date_from: str = None, date_to: str = None):
    """Get statistics aggregated by product tags"""
    today_start, start_date, end_date = _parse_date_range(date_from, date_to)

    if not database.connected or database.orders is None or database.products is None:
        return {"tags": []}

    all_tags = list(database.product_tags.find()) if database.product_tags else []
    tag_map = {str(t["_id"]): t["name"] for t in all_tags}

    products = list(database.products.find({"tags": {"$exists": True, "$ne": []}}))
    product_tags_map = {str(p["_id"]): p.get("tags", []) for p in products}

    pipeline = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}, "status": {"$ne": "cancelled"}}},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "count": {"$sum": "$items.qty"},
            "revenue": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}}
        }}
    ]
    product_stats = list(database.orders.aggregate(pipeline))

    tag_stats = {}
    for stat in product_stats:
        product_id = stat["_id"]
        tags = product_tags_map.get(product_id, [])
        for tag_id in tags:
            if tag_id not in tag_stats:
                tag_stats[tag_id] = {"count": 0, "revenue": 0}
            tag_stats[tag_id]["count"] += stat["count"]
            tag_stats[tag_id]["revenue"] += stat["revenue"]

    result = []
    for tag_id, stats in tag_stats.items():
        tag_name = tag_map.get(tag_id, "Невідомий тег")
        result.append({
            "tag_id": tag_id,
            "tag_name": tag_name,
            "count": stats["count"],
            "revenue": stats["revenue"]
        })

    result.sort(key=lambda x: x["revenue"], reverse=True)
    return {"tags": result}


@router.get("/stats/by-product/{product_id}")
async def get_stats_by_product(product_id: str, date_from: str = None, date_to: str = None):
    """Get detailed statistics for a specific product"""
    today_start, start_date, end_date = _parse_date_range(date_from, date_to, default_days=30)

    if not database.connected or database.orders is None or database.products is None:
        return {"product": None, "stats": {}}

    product = database.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    pipeline = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}, "status": {"$ne": "cancelled"}}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$group": {
            "_id": None,
            "total_qty": {"$sum": "$items.qty"},
            "total_revenue": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}},
            "order_count": {"$sum": 1}
        }}
    ]
    stats_result = list(database.orders.aggregate(pipeline))
    stats = stats_result[0] if stats_result else {"total_qty": 0, "total_revenue": 0, "order_count": 0}

    days_in_range = (end_date - start_date).days + 1

    # Optimized: single aggregation instead of N queries
    daily_product_pipeline = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}, "status": {"$ne": "cancelled"}}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "qty": {"$sum": "$items.qty"},
            "revenue": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_results = {r["_id"]: r for r in database.orders.aggregate(daily_product_pipeline)}

    daily_stats = []
    for i in range(min(days_in_range, 30)):
        day = start_date + timedelta(days=i)
        day_key = day.strftime("%Y-%m-%d")
        day_data = daily_results.get(day_key, {"qty": 0, "revenue": 0})
        daily_stats.append({
            "date": day.strftime("%d.%m"),
            "qty": day_data["qty"],
            "revenue": day_data["revenue"]
        })

    return {
        "product": serialize_doc(product),
        "stats": {
            "total_qty": stats.get("total_qty", 0),
            "total_revenue": stats.get("total_revenue", 0),
            "order_count": stats.get("order_count", 0)
        },
        "daily_stats": daily_stats
    }


# ============ Export ============

@router.get("/export/orders")
async def export_orders(date_from: str = None, date_to: str = None):
    """Export orders to CSV format"""
    _, start_date, end_date = _parse_date_range(date_from, date_to)

    if not database.connected or database.orders is None:
        orders = DEMO_ORDERS
    else:
        orders = list(database.orders.find({
            "created_at": {"$gte": start_date, "$lte": end_date}
        }).sort("created_at", -1))

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow(['№ Замовлення', 'Дата', 'Тип', 'Столик', 'Клієнт', 'Телефон', 'Товари', 'Сума', 'Статус', 'Оплата'])

    order_types = {'dine_in': 'В залі', 'takeaway': 'З собою', 'delivery': 'Доставка'}
    statuses = {'new': 'Нове', 'preparing': 'Готується', 'ready': 'Готове', 'completed': 'Виконано', 'cancelled': 'Скасовано'}
    payment_statuses = {'pending': 'Очікує', 'paid': 'Оплачено'}

    for order in orders:
        created = order.get('created_at')
        if isinstance(created, datetime):
            date_str = created.strftime('%d.%m.%Y %H:%M')
        elif isinstance(created, str):
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                date_str = dt.strftime('%d.%m.%Y %H:%M')
            except:
                date_str = created
        else:
            date_str = ''

        items_str = ', '.join([f"{item.get('name', '')} x{item.get('qty', 1)}" for item in order.get('items', [])])

        writer.writerow([
            order.get('order_number', ''),
            date_str,
            order_types.get(order.get('order_type', ''), order.get('order_type', '')),
            order.get('table_number', '') or '',
            order.get('customer_name', '') or '',
            order.get('customer_phone', '') or '',
            items_str,
            order.get('total', 0),
            statuses.get(order.get('status', ''), order.get('status', '')),
            payment_statuses.get(order.get('payment_status', ''), order.get('payment_status', ''))
        ])

    csv_content = '\ufeff' + output.getvalue()
    output.close()

    filename = f"orders_{date_from or 'all'}_{date_to or 'now'}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/stats")
async def export_stats(date_from: str = None, date_to: str = None):
    """Export daily statistics to CSV format"""
    _, start_date, end_date = _parse_date_range(date_from, date_to)

    days_in_range = (end_date - start_date).days + 1

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow(['Дата', 'Замовлень', 'Виручка (грн)', 'В залі', 'З собою', 'Доставка'])

    if not database.connected or database.orders is None:
        for i in range(min(days_in_range, 30)):
            day = start_date + timedelta(days=i)
            writer.writerow([day.strftime('%d.%m.%Y'), 0, 0, 0, 0, 0])
    else:
        # Optimized: single aggregation instead of N queries
        export_pipeline = [
            {"$match": {
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": {"$ne": "cancelled"}
            }},
            {"$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "order_type": "$order_type"
                },
                "count": {"$sum": 1},
                "revenue": {"$sum": "$total"}
            }}
        ]
        agg_results = list(database.orders.aggregate(export_pipeline))

        # Build lookup dict: {date: {order_type: {count, revenue}}}
        daily_data = {}
        for r in agg_results:
            date_key = r["_id"]["date"]
            order_type = r["_id"]["order_type"]
            if date_key not in daily_data:
                daily_data[date_key] = {"total": 0, "revenue": 0, "dine_in": 0, "takeaway": 0, "delivery": 0}
            daily_data[date_key]["total"] += r["count"]
            daily_data[date_key]["revenue"] += r["revenue"]
            if order_type in ["dine_in", "takeaway", "delivery"]:
                daily_data[date_key][order_type] += r["count"]

        for i in range(min(days_in_range, 30)):
            day = start_date + timedelta(days=i)
            day_key = day.strftime("%Y-%m-%d")
            data = daily_data.get(day_key, {"total": 0, "revenue": 0, "dine_in": 0, "takeaway": 0, "delivery": 0})

            writer.writerow([
                day.strftime('%d.%m.%Y'),
                data["total"],
                data["revenue"],
                data["dine_in"],
                data["takeaway"],
                data["delivery"]
            ])

    writer.writerow([])
    writer.writerow(['=== Топ продуктів ==='])
    writer.writerow(['Назва', 'Кількість', 'Виручка (грн)'])

    if database.connected and database.orders is not None:
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}, "status": {"$ne": "cancelled"}}},
            {"$unwind": "$items"},
            {"$group": {
                "_id": "$items.name",
                "count": {"$sum": "$items.qty"},
                "revenue": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}}
            }},
            {"$sort": {"revenue": -1}},
            {"$limit": 20}
        ]
        top_products = list(database.orders.aggregate(pipeline))
        for product in top_products:
            writer.writerow([product['_id'], product['count'], product['revenue']])

    csv_content = '\ufeff' + output.getvalue()
    output.close()

    filename = f"stats_{date_from or 'all'}_{date_to or 'now'}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
