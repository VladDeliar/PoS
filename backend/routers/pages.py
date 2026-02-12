from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .. import database
from ..config import RESTAURANT_NAME, RESTAURANT_ADDRESS, RESTAURANT_PHONE, RESTAURANT_HOURS
from ..dependencies import templates, runtime_settings
from ..utils.data_fetchers import get_categories_list, get_products_list, get_menu_items_list

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

    # Auto-migrate v1 to v2 format
    if storefront and storefront.get("version") != 2:
        from .settings import migrate_v1_to_v2
        storefront = migrate_v1_to_v2(storefront)

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
