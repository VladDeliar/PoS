from datetime import datetime

from .. import database
from ..utils.demo_data import demo_state


def generate_order_number():
    """Generate unique order number"""
    today = datetime.utcnow().strftime("%Y%m%d")
    if database.connected and database.orders is not None:
        count = database.orders.count_documents({
            "created_at": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0)}
        })
    else:
        demo_state.order_counter += 1
        count = demo_state.order_counter
    return f"ORD-{today}-{count:03d}"
