"""
Site Pages API Router.

Provides CRUD operations for custom informational site pages,
including image upload support.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from bson import ObjectId
from pymongo import ReturnDocument, UpdateOne

from .. import database
from ..models import SitePageCreate, SitePageUpdate
from ..utils.serializers import serialize_all
from ..redis_manager import redis_manager, CACHE_SITE_PAGES, TTL_SITE_PAGES

router = APIRouter(prefix="/api/site-pages", tags=["site-pages"])

# Upload directories
BASE_DIR = Path(__file__).parent.parent.parent
PAGES_UPLOAD_DIR = BASE_DIR / "frontend" / "static" / "uploads" / "pages"
SECTIONS_UPLOAD_DIR = BASE_DIR / "frontend" / "static" / "uploads" / "sections"
PAGES_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SECTIONS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 3 * 1024 * 1024  # 3 MB


def _validate_and_save_file(contents: bytes, filename: str, dest_dir: Path, url_prefix: str) -> str:
    """Validate file extension/size and write to disk. Returns public URL."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Тільки JPG або PNG файли")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Файл занадто великий (макс. 3 МБ)")
    fname = f"{uuid.uuid4().hex}{ext}"
    (dest_dir / fname).write_bytes(contents)
    return f"{url_prefix}{fname}"


def _delete_file_safe(url_path: str):
    """Delete a file from disk given its /static/... URL. Ignores missing files."""
    if not url_path or not url_path.startswith("/static/uploads/"):
        return
    relative = url_path.lstrip("/")  # static/uploads/pages/abc.jpg
    full_path = BASE_DIR / "frontend" / relative
    try:
        os.remove(full_path)
    except FileNotFoundError:
        pass


def _collect_page_images(page_doc: dict) -> list:
    """Collect all image URLs from a page document."""
    images = []
    if page_doc.get("cover_image"):
        images.append(page_doc["cover_image"])
    for section in page_doc.get("sections", []):
        images.extend(section.get("images", []))
    return images


# ─── List / Get ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_site_pages(published_only: bool = False):
    """Return all site pages sorted by sort_order."""
    cached = await redis_manager.get_cached(CACHE_SITE_PAGES)
    if cached is not None:
        if published_only:
            return [p for p in cached if p.get("is_published")]
        return cached

    if not database.connected or database.site_pages is None:
        return []

    pages = list(database.site_pages.find().sort("sort_order", 1))
    result = [serialize_all(p) for p in pages]

    await redis_manager.set_cached(CACHE_SITE_PAGES, result, TTL_SITE_PAGES)

    if published_only:
        return [p for p in result if p.get("is_published")]
    return result


@router.get("/{page_id}")
async def get_site_page(page_id: str):
    """Get a single site page by ID."""
    if not database.connected or database.site_pages is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(page_id):
        raise HTTPException(status_code=400, detail="Invalid page ID")

    page = database.site_pages.find_one({"_id": ObjectId(page_id)})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    return serialize_all(page)


# ─── Image delete (must be before /{page_id} DELETE to avoid shadowing) ───────

@router.delete("/image")
async def delete_image(path: str = Query(...)):
    """Delete a single uploaded image file by its /static/uploads/... path."""
    if not path.startswith("/static/uploads/"):
        raise HTTPException(status_code=400, detail="Invalid image path")

    _delete_file_safe(path)
    return {"status": "deleted"}


# ─── Create / Update / Delete ─────────────────────────────────────────────────

@router.post("/")
async def create_site_page(data: SitePageCreate):
    """Create a new site page."""
    if not database.connected or database.site_pages is None:
        raise HTTPException(status_code=503, detail="Database not available")

    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()

    result = database.site_pages.insert_one(doc)
    doc["_id"] = result.inserted_id

    await redis_manager.invalidate_key(CACHE_SITE_PAGES)
    return serialize_all(doc)


@router.put("/{page_id}")
async def update_site_page(page_id: str, data: SitePageUpdate):
    """Partial update of a site page."""
    if not database.connected or database.site_pages is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(page_id):
        raise HTTPException(status_code=400, detail="Invalid page ID")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.utcnow()

    updated = database.site_pages.find_one_and_update(
        {"_id": ObjectId(page_id)},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Page not found")

    await redis_manager.invalidate_key(CACHE_SITE_PAGES)
    return serialize_all(updated)


@router.delete("/{page_id}")
async def delete_site_page(page_id: str):
    """Delete a site page and all its uploaded images."""
    if not database.connected or database.site_pages is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(page_id):
        raise HTTPException(status_code=400, detail="Invalid page ID")

    page = database.site_pages.find_one({"_id": ObjectId(page_id)})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Delete all associated image files from disk
    for img_url in _collect_page_images(page):
        _delete_file_safe(img_url)

    database.site_pages.delete_one({"_id": ObjectId(page_id)})

    await redis_manager.invalidate_key(CACHE_SITE_PAGES)
    return {"status": "deleted", "page_id": page_id}


# ─── Reorder ──────────────────────────────────────────────────────────────────

@router.post("/reorder")
async def reorder_site_pages(items: list):
    """
    Accept [{id, sort_order}, ...] and bulk-update sort_order.
    """
    if not database.connected or database.site_pages is None:
        raise HTTPException(status_code=503, detail="Database not available")

    operations = []
    for item in items:
        if not ObjectId.is_valid(item.get("id", "")):
            continue
        operations.append(
            UpdateOne(
                {"_id": ObjectId(item["id"])},
                {"$set": {"sort_order": item["sort_order"]}}
            )
        )

    if operations:
        database.site_pages.bulk_write(operations)

    await redis_manager.invalidate_key(CACHE_SITE_PAGES)
    return {"status": "reordered", "count": len(operations)}


# ─── Image Upload ──────────────────────────────────────────────────────────────

@router.post("/{page_id}/upload-image")
async def upload_page_image(page_id: str, file: UploadFile = File(...)):
    """Upload a cover image for a page. Returns the public URL."""
    if not database.connected or database.site_pages is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(page_id):
        raise HTTPException(status_code=400, detail="Invalid page ID")

    contents = await file.read()
    url = _validate_and_save_file(contents, file.filename, PAGES_UPLOAD_DIR, "/static/uploads/pages/")
    return {"url": url}


@router.post("/{page_id}/sections/{section_id}/upload-image")
async def upload_section_image(page_id: str, section_id: str, file: UploadFile = File(...)):
    """Upload an image for a section. Returns the public URL."""
    if not database.connected or database.site_pages is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(page_id):
        raise HTTPException(status_code=400, detail="Invalid page ID")

    contents = await file.read()
    url = _validate_and_save_file(contents, file.filename, SECTIONS_UPLOAD_DIR, "/static/uploads/sections/")
    return {"url": url}
