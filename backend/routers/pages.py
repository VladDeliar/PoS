from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from bson import ObjectId

from .. import database
from ..config import RESTAURANT_NAME, RESTAURANT_ADDRESS, RESTAURANT_PHONE, RESTAURANT_HOURS
from ..dependencies import templates, runtime_settings
from ..utils.data_fetchers import get_categories_list, get_products_list, get_menu_items_list
from ..utils.serializers import serialize_all

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "restaurant_name": RESTAURANT_NAME
    })


@router.get("/menu", response_class=HTMLResponse)
async def menu_page(request: Request):
    cats = get_categories_list()
    prods = get_menu_items_list(active_only=True)
    if not prods:
        prods = get_products_list(available_only=True)

    # Load storefront config
    storefront = runtime_settings.get("storefront", {})
    if database.connected and database.settings is not None:
        db_settings = database.settings.find_one({"_id": "app_settings"})
        if db_settings and db_settings.get("storefront"):
            storefront = db_settings["storefront"]

    # Load order types
    order_types = []
    if database.connected and database.settings is not None:
        db_settings_ot = database.settings.find_one({"_id": "app_settings"})
        if db_settings_ot and db_settings_ot.get("order_types"):
            order_types = [ot for ot in db_settings_ot["order_types"] if ot.get("enabled", True)]
            order_types = sorted(order_types, key=lambda x: x.get("sort_order", 0))
    if not order_types:
        order_types = runtime_settings.get("order_types", [])
        order_types = [ot for ot in order_types if ot.get("enabled", True)]
        order_types = sorted(order_types, key=lambda x: x.get("sort_order", 0))

    # Extract font family for server-side Google Fonts link
    font_family = storefront.get("branding", {}).get("fontFamily", "system")
    font_map = {
        "inter": "Inter",
        "roboto": "Roboto",
        "open-sans": "Open Sans",
        "lato": "Lato",
        "nunito": "Nunito"
    }
    font_display_name = font_map.get(font_family)

    # Load media slider
    media_slider = {"enabled": False, "items": []}
    if db_settings and db_settings.get("media_slider"):
        slider_cfg = db_settings["media_slider"]
        if slider_cfg.get("enabled") and slider_cfg.get("items"):
            media_slider = slider_cfg

    # Auto-migrate v1 to v2 format
    if storefront and storefront.get("version") != 2:
        from .settings import migrate_v1_to_v2
        storefront = migrate_v1_to_v2(storefront)

    # Load card surcharge percent
    card_surcharge_percent = 0
    surcharge_data = runtime_settings.get("card_surcharge", {})
    if not surcharge_data and database.connected and database.settings is not None:
        db_cs = database.settings.find_one({"_id": "app_settings"})
        if db_cs and db_cs.get("card_surcharge"):
            surcharge_data = db_cs["card_surcharge"]
    card_surcharge_percent = surcharge_data.get("percent", 0) if surcharge_data else 0

    return templates.TemplateResponse("menu.html", {
        "request": request,
        "categories": cats,
        "products": prods,
        "restaurant_name": RESTAURANT_NAME,
        "restaurant_address": RESTAURANT_ADDRESS,
        "restaurant_phone": RESTAURANT_PHONE,
        "restaurant_hours": RESTAURANT_HOURS,
        "storefront_config": storefront,
        "font_family": font_display_name,
        "order_types": order_types,
        "card_surcharge_percent": card_surcharge_percent,
        "media_slider": media_slider,
    })


@router.get("/track/{order_id}", response_class=HTMLResponse)
async def track_order_page(request: Request, order_id: str):
    """Order tracking page for customers"""
    return templates.TemplateResponse("track_order.html", {
        "request": request,
        "order_id": order_id,
        "restaurant_name": RESTAURANT_NAME,
        "restaurant_phone": RESTAURANT_PHONE
    })


@router.get("/pages/{page_id}", response_class=HTMLResponse)
async def site_page_view(request: Request, page_id: str):
    """Public customer-facing view of a single site page."""
    if not database.connected or database.site_pages is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(page_id):
        raise HTTPException(status_code=404, detail="Page not found")

    page = database.site_pages.find_one({"_id": ObjectId(page_id), "is_published": True})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    return templates.TemplateResponse("site_page.html", {
        "request": request,
        "page": serialize_all(page),
        "restaurant_name": RESTAURANT_NAME,
    })


@router.get("/pos", response_class=HTMLResponse)
async def pos_page(request: Request):
    cats = get_categories_list()
    prods = get_menu_items_list(active_only=True)
    if not prods:
        prods = get_products_list(available_only=True)
    return templates.TemplateResponse("pos.html", {
        "request": request,
        "categories": cats,
        "products": prods
    })
