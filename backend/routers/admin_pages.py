from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from bson import ObjectId

from .. import database
from ..dependencies import templates
from ..utils.serializers import serialize_all
from ..utils.data_fetchers import get_categories_list
from ..redis_manager import redis_manager, CACHE_MODIFIERS, TTL_MODIFIERS

router = APIRouter(prefix="/admin", tags=["admin"])


async def _get_modifiers_cached():
    """Get modifiers with Redis caching."""
    cached = await redis_manager.get_cached(CACHE_MODIFIERS)
    if cached is not None:
        return cached
    if not database.connected or database.modifiers is None:
        return []
    mods = [serialize_all(doc) for doc in database.modifiers.find()]
    await redis_manager.set_cached(CACHE_MODIFIERS, mods, TTL_MODIFIERS)
    return mods


@router.get("/orders", response_class=HTMLResponse)
async def admin_orders_page(request: Request):
    return templates.TemplateResponse("admin/orders.html", {"request": request})


@router.get("/assortment", response_class=HTMLResponse)
async def admin_assortment_page(request: Request):
    """Assortment management page (all products catalog)"""
    cats = get_categories_list()
    return templates.TemplateResponse("admin/assortment.html", {
        "request": request,
        "categories": cats
    })


@router.get("/menu", response_class=HTMLResponse)
async def admin_menu_page(request: Request):
    """Menu management page (active menu items)"""
    cats = get_categories_list()
    return templates.TemplateResponse("admin/menu.html", {
        "request": request,
        "categories": cats
    })


@router.get("/dishes", response_class=HTMLResponse)
async def admin_dishes_page(request: Request):
    """Modern dashboard for managing active menu dishes and modifiers"""
    cats = get_categories_list()
    return templates.TemplateResponse("admin/dishes.html", {
        "request": request,
        "categories": cats
    })


@router.get("/dishes/create", response_class=HTMLResponse)
async def admin_dish_create_page(request: Request):
    """Page for creating a new dish"""
    cats = get_categories_list()
    mods = await _get_modifiers_cached()
    tags = []
    if database.connected and database.product_tags is not None:
        tags = [serialize_all(doc) for doc in database.product_tags.find()]
    return templates.TemplateResponse("admin/dish_form.html", {
        "request": request,
        "categories": cats,
        "modifiers": mods,
        "tags": tags,
        "dish": None,
        "mode": "create",
        "prev_dish_id": None,
        "next_dish_id": None
    })


@router.get("/dishes/edit/{dish_id}", response_class=HTMLResponse)
async def admin_dish_edit_page(request: Request, dish_id: str):
    """Page for editing an existing dish"""
    if not database.connected or database.products is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    dish = database.products.find_one({"_id": ObjectId(dish_id)})
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")

    cats = get_categories_list()
    mods = await _get_modifiers_cached()
    tags = []
    if database.product_tags is not None:
        tags = [serialize_all(doc) for doc in database.product_tags.find()]

    all_dishes = list(database.products.find({}, {"_id": 1}).sort("_id", 1))
    all_dish_ids = [str(d["_id"]) for d in all_dishes]

    current_index = all_dish_ids.index(dish_id) if dish_id in all_dish_ids else -1
    prev_dish_id = all_dish_ids[current_index - 1] if current_index > 0 else None
    next_dish_id = all_dish_ids[current_index + 1] if current_index >= 0 and current_index < len(all_dish_ids) - 1 else None

    return templates.TemplateResponse("admin/dish_form.html", {
        "request": request,
        "categories": cats,
        "modifiers": mods,
        "tags": tags,
        "dish": serialize_all(dish),
        "mode": "edit",
        "prev_dish_id": prev_dish_id,
        "next_dish_id": next_dish_id
    })


@router.get("/categories", response_class=HTMLResponse)
async def admin_categories_page(request: Request):
    return templates.TemplateResponse("admin/categories.html", {"request": request})


@router.get("/stats", response_class=HTMLResponse)
async def admin_stats_page(request: Request):
    return templates.TemplateResponse("admin/stats.html", {"request": request})


@router.get("/production", response_class=HTMLResponse)
async def admin_production_page(request: Request):
    categories = get_categories_list()
    return templates.TemplateResponse("admin/production.html", {"request": request, "categories": categories})


@router.get("/tags", response_class=HTMLResponse)
async def admin_tags_page(request: Request):
    return templates.TemplateResponse("admin/tags.html", {"request": request})


@router.get("/projects", response_class=HTMLResponse)
async def admin_projects_page(request: Request):
    return templates.TemplateResponse("admin/projects.html", {"request": request})


@router.get("/audit-logs", response_class=HTMLResponse)
async def admin_audit_logs_page(request: Request):
    return templates.TemplateResponse("admin/audit_logs.html", {"request": request})


@router.get("/feedbacks", response_class=HTMLResponse)
async def admin_feedbacks_page(request: Request):
    return templates.TemplateResponse("admin/feedbacks.html", {"request": request})


@router.get("/promo-codes", response_class=HTMLResponse)
async def admin_promo_codes_page(request: Request):
    return templates.TemplateResponse("admin/promo_codes.html", {"request": request})


@router.get("/qr-codes", response_class=HTMLResponse)
async def admin_qr_codes_page(request: Request):
    return templates.TemplateResponse("admin/qr_codes.html", {"request": request})


@router.get("/modifiers", response_class=HTMLResponse)
async def admin_modifiers_page(request: Request):
    return templates.TemplateResponse("admin/modifiers.html", {"request": request})


@router.get("/combos", response_class=HTMLResponse)
async def admin_combos_page(request: Request):
    return templates.TemplateResponse("admin/combos.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request):
    return templates.TemplateResponse("admin/settings.html", {"request": request})


@router.get("/delivery-zones", response_class=HTMLResponse)
async def admin_delivery_zones_page(request: Request):
    return templates.TemplateResponse("admin/delivery_zones.html", {"request": request})


@router.get("/store-design", response_class=HTMLResponse)
async def admin_store_design_page(request: Request):
    return templates.TemplateResponse("admin/store_design.html", {"request": request})


