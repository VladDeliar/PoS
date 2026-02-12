from typing import List
from uuid import uuid4

from fastapi import APIRouter, Request

from .. import database
from ..dependencies import runtime_settings
from ..models import StorefrontConfig, PageBuilderConfig

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/")
async def get_settings():
    """Get all settings"""
    if database.connected and database.settings is not None:
        db_settings = database.settings.find_one({"_id": "app_settings"})
        if db_settings:
            if db_settings.get("telegram"):
                runtime_settings["telegram"] = db_settings["telegram"]
            if db_settings.get("restaurant"):
                runtime_settings["restaurant"] = db_settings["restaurant"]
            if db_settings.get("delivery"):
                runtime_settings["delivery"] = db_settings["delivery"]
            if db_settings.get("order_types"):
                runtime_settings["order_types"] = db_settings["order_types"]
            if db_settings.get("storefront"):
                runtime_settings["storefront"] = db_settings["storefront"]

    return runtime_settings


@router.post("/telegram")
async def save_telegram_settings(bot_token: str = "", chat_id: str = ""):
    """Save Telegram bot settings"""
    runtime_settings["telegram"] = {
        "bot_token": bot_token,
        "chat_id": chat_id
    }

    if database.connected and database.settings is not None:
        database.settings.update_one(
            {"_id": "app_settings"},
            {"$set": {"telegram": runtime_settings["telegram"]}},
            upsert=True
        )

    return {"status": "saved"}


@router.post("/telegram/test")
async def test_telegram():
    """Send a test Telegram message"""
    from ..telegram_bot import send_telegram_message

    settings = runtime_settings.get("telegram", {})
    if not settings.get("bot_token") or not settings.get("chat_id"):
        return {"success": False, "error": "Telegram не налаштовано"}

    success = await send_telegram_message(
        "Тестове повідомлення від POS системи!",
        chat_id=settings["chat_id"],
        token=settings["bot_token"]
    )
    return {"success": success, "error": None if success else "Не вдалося надіслати"}


@router.post("/restaurant")
async def save_restaurant_settings(name: str = "", address: str = "", phone: str = "", hours: str = ""):
    """Save restaurant settings"""
    runtime_settings["restaurant"] = {
        "name": name,
        "address": address,
        "phone": phone,
        "hours": hours
    }

    if database.connected and database.settings is not None:
        database.settings.update_one(
            {"_id": "app_settings"},
            {"$set": {"restaurant": runtime_settings["restaurant"]}},
            upsert=True
        )

    return {"status": "saved"}


@router.get("/delivery")
async def get_delivery_settings():
    """Get delivery settings"""
    if database.connected and database.settings is not None:
        db_settings = database.settings.find_one({"_id": "app_settings"})
        if db_settings and db_settings.get("delivery"):
            runtime_settings["delivery"] = db_settings["delivery"]
    return runtime_settings.get("delivery", {})


@router.post("/delivery")
async def save_delivery_settings(
    min_order_amount: float = 0,
    min_order_amount_out_of_city: float = 0,
    min_order_message: str = "",
    enabled: bool = False
):
    """Save delivery settings"""
    runtime_settings["delivery"] = {
        "min_order_amount": min_order_amount,
        "min_order_amount_out_of_city": min_order_amount_out_of_city,
        "min_order_message": min_order_message,
        "enabled": enabled
    }

    if database.connected and database.settings is not None:
        database.settings.update_one(
            {"_id": "app_settings"},
            {"$set": {"delivery": runtime_settings["delivery"]}},
            upsert=True
        )

    return {"status": "saved"}


@router.get("/order-types")
async def get_order_types(enabled_only: bool = False):
    """Get order types configuration"""
    if database.connected and database.settings is not None:
        db_settings = database.settings.find_one({"_id": "app_settings"})
        if db_settings and db_settings.get("order_types"):
            runtime_settings["order_types"] = db_settings["order_types"]

    order_types = runtime_settings.get("order_types", [])
    order_types = sorted(order_types, key=lambda x: x.get("sort_order", 0))

    if enabled_only:
        order_types = [ot for ot in order_types if ot.get("enabled", True)]

    return order_types


@router.post("/order-types")
async def save_order_types(order_types: List[dict]):
    """Save order types configuration"""
    runtime_settings["order_types"] = order_types

    if database.connected and database.settings is not None:
        database.settings.update_one(
            {"_id": "app_settings"},
            {"$set": {"order_types": runtime_settings["order_types"]}},
            upsert=True
        )

    return {"status": "saved"}


@router.put("/order-types/reorder")
async def reorder_order_types(items: List[dict]):
    """Reorder order types by sort_order"""
    for item in items:
        for ot in runtime_settings["order_types"]:
            if ot["type"] == item["type"]:
                ot["sort_order"] = item["sort_order"]
                break

    runtime_settings["order_types"] = sorted(
        runtime_settings["order_types"],
        key=lambda x: x.get("sort_order", 0)
    )

    if database.connected and database.settings is not None:
        database.settings.update_one(
            {"_id": "app_settings"},
            {"$set": {"order_types": runtime_settings["order_types"]}},
            upsert=True
        )

    return {"status": "saved", "order_types": runtime_settings["order_types"]}


def _uid():
    return str(uuid4())[:8]


def migrate_v1_to_v2(old: dict) -> dict:
    """Convert old StorefrontConfig (v1) to PageBuilderConfig (v2)"""
    sections = []
    blocks = sorted(old.get("blocks", []), key=lambda b: b.get("sort_order", 0))

    announcement_data = old.get("announcement", {})
    hero_data = old.get("heroBanner", {})
    components = old.get("components", {})
    store_info = old.get("storeInfo", {})

    for block in blocks:
        block_id = block.get("id", "")
        el_settings = {}
        el_type = block_id

        if block_id == "announcement":
            el_settings = {
                "text": announcement_data.get("text", ""),
                "bgColor": announcement_data.get("bgColor", "#FFF3E0"),
                "textColor": announcement_data.get("textColor", "#E65100"),
            }
        elif block_id == "hero_banner":
            el_type = "image"
            el_settings = {
                "imageUrl": hero_data.get("imageUrl", ""),
                "altText": hero_data.get("altText", ""),
                "linkUrl": hero_data.get("linkUrl", ""),
                "width": "100%",
                "borderRadius": "8px",
            }
        elif block_id == "menu":
            el_settings = {
                "productViewMode": components.get("productViewMode", "list"),
                "navPosition": components.get("navPosition", "sidebar"),
                "cardStyle": components.get("cardStyle", "default"),
            }
        elif block_id == "hours":
            el_settings = {"showIcon": True}
        elif block_id == "address":
            el_settings = {
                "showMap": bool(store_info.get("googleMapsEmbedUrl")),
                "showCopyButton": store_info.get("showCopyButtons", True),
            }
        elif block_id == "phone":
            el_settings = {
                "showCopyButton": store_info.get("showCopyButtons", True),
            }

        section = {
            "id": _uid(),
            "label": block.get("label", block_id),
            "collapsed": False,
            "visible": block.get("enabled", True),
            "sort_order": block.get("sort_order", 0),
            "settings": {},
            "rows": [{
                "id": _uid(),
                "visible": True,
                "sort_order": 0,
                "settings": {},
                "columns": [{
                    "id": _uid(),
                    "width": "1/1",
                    "sort_order": 0,
                    "settings": {},
                    "elements": [{
                        "id": _uid(),
                        "type": el_type,
                        "label": block.get("label", ""),
                        "visible": True,
                        "sort_order": 0,
                        "settings": el_settings,
                    }],
                }],
            }],
        }
        sections.append(section)

    # If store_info has googleMapsEmbedUrl but no address block with map, add map section
    maps_url = store_info.get("googleMapsEmbedUrl", "")
    if maps_url:
        # Check if address block already references the map
        has_map = any(
            s["rows"][0]["columns"][0]["elements"][0]["type"] == "map"
            for s in sections
            if s.get("rows") and s["rows"][0].get("columns") and s["rows"][0]["columns"][0].get("elements")
        )
        if not has_map:
            sections.append({
                "id": _uid(),
                "label": "Map",
                "collapsed": False,
                "visible": True,
                "sort_order": len(sections),
                "settings": {},
                "rows": [{
                    "id": _uid(),
                    "visible": True,
                    "sort_order": 0,
                    "settings": {},
                    "columns": [{
                        "id": _uid(),
                        "width": "1/1",
                        "sort_order": 0,
                        "settings": {},
                        "elements": [{
                            "id": _uid(),
                            "type": "map",
                            "label": "Google Map",
                            "visible": True,
                            "sort_order": 0,
                            "settings": {
                                "googleMapsEmbedUrl": maps_url,
                                "height": "300px",
                            },
                        }],
                    }],
                }],
            })

    return {
        "version": 2,
        "sections": sections,
        "branding": old.get("branding", {
            "accentColor": "#4CAF50",
            "fontFamily": "system",
            "borderRadius": "default",
        }),
        "globalSettings": {},
    }


@router.get("/storefront")
async def get_storefront_settings():
    """Get storefront layout configuration (auto-migrates v1 to v2)"""
    if database.connected and database.settings is not None:
        db_settings = database.settings.find_one({"_id": "app_settings"})
        if db_settings and db_settings.get("storefront"):
            runtime_settings["storefront"] = db_settings["storefront"]

    storefront = runtime_settings.get("storefront", {})

    # Auto-migrate v1 to v2
    if storefront and storefront.get("version") != 2:
        # Old format detected - backward compat
        if storefront.get("layout") == "sidebar":
            storefront["layout"] = "sidebar-right"
        storefront = migrate_v1_to_v2(storefront)

    return storefront


@router.post("/storefront")
async def save_storefront_settings(request: Request):
    """Save storefront layout configuration (accepts v1 or v2 format)"""
    data = await request.json()

    # Detect format by version field
    if data.get("version") == 2:
        config = PageBuilderConfig(**data)
        storefront_data = config.model_dump()
    else:
        config = StorefrontConfig(**data)
        storefront_data = config.model_dump()

    runtime_settings["storefront"] = storefront_data

    if database.connected and database.settings is not None:
        database.settings.update_one(
            {"_id": "app_settings"},
            {"$set": {"storefront": storefront_data}},
            upsert=True
        )

    return {"status": "saved"}
