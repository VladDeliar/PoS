from pathlib import Path
from fastapi.templating import Jinja2Templates
from .config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    RESTAURANT_NAME, RESTAURANT_ADDRESS, RESTAURANT_PHONE, RESTAURANT_HOURS
)

# Шлях до frontend/templates
BASE_DIR = Path(__file__).parent.parent  # Повертаємось до кореня проекту
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))

runtime_settings = {
    "telegram": {
        "bot_token": TELEGRAM_BOT_TOKEN,
        "chat_id": TELEGRAM_CHAT_ID
    },
    "restaurant": {
        "name": RESTAURANT_NAME,
        "address": RESTAURANT_ADDRESS,
        "phone": RESTAURANT_PHONE,
        "hours": RESTAURANT_HOURS
    },
    "delivery": {
        "min_order_amount": 0,
        "min_order_amount_out_of_city": 0,
        "min_order_message": "Мінімальна сума для доставки: {amount} грн",
        "enabled": False
    },
    "order_types": [
        {"type": "dine_in", "label": "В залі", "enabled": True, "sort_order": 0},
        {"type": "takeaway", "label": "З собою", "enabled": True, "sort_order": 1},
        {"type": "delivery", "label": "Доставка", "enabled": True, "sort_order": 2},
        {"type": "self_service", "label": "Самообслуговування", "enabled": True, "sort_order": 3}
    ],
    "storefront": {
        "preset": "custom",
        "layout": "sidebar-right",
        "blocks": [
            {"id": "announcement", "label": "Announcement Bar", "enabled": False, "sort_order": 0, "locked": False},
            {"id": "hero_banner", "label": "Hero Banner", "enabled": False, "sort_order": 1, "locked": False},
            {"id": "menu", "label": "Menu", "enabled": True, "sort_order": 2, "locked": True},
            {"id": "hours", "label": "Operating Hours", "enabled": True, "sort_order": 3, "locked": False},
            {"id": "address", "label": "Address & Map", "enabled": True, "sort_order": 4, "locked": False},
            {"id": "phone", "label": "Contact Phone", "enabled": True, "sort_order": 5, "locked": False},
        ],
        "components": {
            "productViewMode": "list",
            "navPosition": "sidebar",
            "cardStyle": "default"
        },
        "branding": {
            "accentColor": "#4CAF50",
            "fontFamily": "system",
            "borderRadius": "default"
        },
        "announcement": {
            "text": "",
            "bgColor": "#FFF3E0",
            "textColor": "#E65100"
        },
        "heroBanner": {
            "imageUrl": "",
            "altText": "",
            "linkUrl": ""
        },
        "storeInfo": {
            "googleMapsEmbedUrl": "",
            "showCopyButtons": True,
            "infoPlacement": "sidebar"
        }
    }
}
