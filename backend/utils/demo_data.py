DEMO_CATEGORIES = [
    {"_id": "1", "name": "Кава", "icon": "coffee", "sort_order": 1},
    {"_id": "2", "name": "Напої", "icon": "cup", "sort_order": 2},
    {"_id": "3", "name": "Десерти", "icon": "cake", "sort_order": 3},
]

DEMO_PRODUCTS = [
    {"_id": "1", "name": "Капучіно", "category_id": "1", "price": 65, "description": "Класичний капучіно", "image": "/static/img/placeholder.svg", "weight": "250 мл", "cook_time": "5 хв", "available": True},
    {"_id": "2", "name": "Лате", "category_id": "1", "price": 70, "description": "Ніжний лате", "image": "/static/img/placeholder.svg", "weight": "300 мл", "cook_time": "5 хв", "available": True},
    {"_id": "3", "name": "Американо", "category_id": "1", "price": 50, "description": "Класичний американо", "image": "/static/img/placeholder.svg", "weight": "200 мл", "cook_time": "3 хв", "available": True},
    {"_id": "4", "name": "Лимонад", "category_id": "2", "price": 55, "description": "Домашній лимонад", "image": "/static/img/placeholder.svg", "weight": "400 мл", "cook_time": "2 хв", "available": True},
    {"_id": "5", "name": "Чізкейк", "category_id": "3", "price": 95, "description": "Ніжний чізкейк", "image": "/static/img/placeholder.svg", "weight": "150 г", "cook_time": "-", "available": True},
]

DEMO_MENU_ITEMS = []
DEMO_ORDERS = []
DEMO_COMBOS = []
DEMO_MODIFIERS = []
DEMO_PROMO_CODES = []
DEMO_FEEDBACKS = []

# Delivery zones demo data
DEMO_ZONES = [
    {
        "_id": "demo_zone_1",
        "name": "Центр",
        "radius_km": 2,
        "color": "#22c55e",
        "delivery_fee": 30,
        "min_order_amount": 200,
        "free_delivery_threshold": 500,
        "enabled": True,
        "priority": 1
    },
    {
        "_id": "demo_zone_2",
        "name": "Середня зона",
        "radius_km": 5,
        "color": "#eab308",
        "delivery_fee": 50,
        "min_order_amount": 300,
        "free_delivery_threshold": 700,
        "enabled": True,
        "priority": 2
    },
    {
        "_id": "demo_zone_3",
        "name": "Далека зона",
        "radius_km": 10,
        "color": "#ef4444",
        "delivery_fee": 80,
        "min_order_amount": 500,
        "free_delivery_threshold": None,
        "enabled": True,
        "priority": 3
    }
]

DEMO_CENTER = {
    "lat": 48.92187972532543,
    "lng": 24.708232677282346,
    "address": "Івано-Франківськ"
}


class DemoState:
    order_counter: int = 0


demo_state = DemoState()
