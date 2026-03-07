from datetime import datetime, timedelta

from .. import database
from ..utils.demo_data import demo_state


def generate_order_number():
    """Generate unique order number"""
    now = datetime.utcnow()
    today = now.strftime("%Y%m%d")
    if database.connected and database.orders is not None:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        count = database.orders.count_documents({
            "created_at": {"$gte": today_start, "$lt": tomorrow_start}
        })
    else:
        demo_state.order_counter += 1
        count = demo_state.order_counter
    return f"ORD-{today}-{count + 1:03d}"
