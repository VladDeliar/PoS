from datetime import datetime

from fastapi import APIRouter, HTTPException
from bson import ObjectId

from .. import database
from ..models import ProductCreate, ProductTagCreate, ProjectCreate
from ..utils.serializers import serialize_doc, serialize_docs, serialize_all
from ..utils.audit import log_action
from ..utils.demo_data import DEMO_PRODUCTS
from ..redis_manager import redis_manager, CACHE_PRODUCT_TAGS, TTL_PRODUCT_TAGS

router = APIRouter(prefix="/api", tags=["products"])


# ============ Products ============

@router.get("/products")
async def get_products(
    category_id: str = None,
    available: bool = None
):
    if not database.connected or database.products is None:
        result = DEMO_PRODUCTS
        if category_id:
            result = [p for p in result if p["category_id"] == category_id]
        if available is not None:
            result = [p for p in result if p.get("available") == available]
        return result

    query = {}
    if category_id:
        query["category_id"] = category_id
    if available is not None:
        query["available"] = available

    products = list(database.products.find(query))

    return serialize_docs(products)


@router.post("/products")
async def create_product(data: ProductCreate):
    if not database.connected or database.products is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    result = database.products.insert_one(doc)

    log_action("create", "product", str(result.inserted_id), data.name)
    response_data = {"_id": str(result.inserted_id), **doc}
    return serialize_all(response_data)


@router.put("/products/{product_id}")
async def update_product(product_id: str, data: ProductCreate):
    if not database.connected or database.products is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    old_product = database.products.find_one({"_id": ObjectId(product_id)})

    result = database.products.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    if old_product:
        changes = {}
        new_data = data.model_dump()
        for key, new_val in new_data.items():
            old_val = old_product.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        if changes:
            log_action("update", "product", product_id, data.name, changes)

    return {"status": "updated"}


@router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    if not database.connected or database.products is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    product = database.products.find_one({"_id": ObjectId(product_id)})
    result = database.products.delete_one({"_id": ObjectId(product_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    if product:
        log_action("delete", "product", product_id, product.get("name", ""))

    return {"status": "deleted"}


@router.post("/products/{product_id}/copy")
async def copy_product(product_id: str):
    """Copy a product with a new ID"""
    if not database.connected or database.products is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    product = database.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    original_name = product.get("name", "")

    del product["_id"]
    product["name"] = f"{original_name} (копія)"
    product["created_at"] = datetime.utcnow()

    result = database.products.insert_one(product)
    product["_id"] = str(result.inserted_id)

    log_action("copy", "product", str(result.inserted_id), product["name"],
               {"copied_from": {"id": product_id, "name": original_name}})

    return serialize_doc(product)


# ============ Product Tags ============

@router.get("/product-tags")
async def get_product_tags():
    """Get all product tags"""
    # Try cache first
    cached = await redis_manager.get_cached(CACHE_PRODUCT_TAGS)
    if cached is not None:
        return cached

    if not database.connected or database.product_tags is None:
        return []

    result = serialize_docs(database.product_tags.find().sort("name", 1))

    # Cache the result
    await redis_manager.set_cached(CACHE_PRODUCT_TAGS, result, TTL_PRODUCT_TAGS)
    return result


@router.post("/product-tags")
async def create_product_tag(data: ProductTagCreate):
    """Create a new product tag"""
    if not database.connected or database.product_tags is None:
        raise HTTPException(status_code=503, detail="Database not available")

    existing = database.product_tags.find_one({"name": data.name})
    if existing:
        raise HTTPException(status_code=400, detail="Тег з такою назвою вже існує")

    tag_doc = data.model_dump()
    result = database.product_tags.insert_one(tag_doc)
    tag_doc["_id"] = str(result.inserted_id)

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_PRODUCT_TAGS)

    return tag_doc


@router.put("/product-tags/{tag_id}")
async def update_product_tag(tag_id: str, data: ProductTagCreate):
    """Update a product tag"""
    if not database.connected or database.product_tags is None:
        raise HTTPException(status_code=503, detail="Database not available")

    existing = database.product_tags.find_one({"name": data.name, "_id": {"$ne": ObjectId(tag_id)}})
    if existing:
        raise HTTPException(status_code=400, detail="Тег з такою назвою вже існує")

    result = database.product_tags.update_one(
        {"_id": ObjectId(tag_id)},
        {"$set": data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_PRODUCT_TAGS)

    updated = database.product_tags.find_one({"_id": ObjectId(tag_id)})
    return serialize_doc(updated)


@router.delete("/product-tags/{tag_id}")
async def delete_product_tag(tag_id: str):
    """Delete a product tag"""
    if not database.connected or database.product_tags is None:
        raise HTTPException(status_code=503, detail="Database not available")

    database.products.update_many(
        {"tags": tag_id},
        {"$pull": {"tags": tag_id}}
    )

    result = database.product_tags.delete_one({"_id": ObjectId(tag_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_PRODUCT_TAGS)

    return {"status": "deleted"}


# ============ Audit Logs ============

@router.get("/audit-logs")
async def get_audit_logs(entity_type: str = None, limit: int = 100):
    """Get audit logs with optional filtering"""
    if not database.connected or database.audit_logs is None:
        return []

    query = {}
    if entity_type:
        query["entity_type"] = entity_type

    logs = list(database.audit_logs.find(query).sort("created_at", -1).limit(limit))
    return serialize_docs(logs)


@router.get("/audit-logs/entity/{entity_type}/{entity_id}")
async def get_entity_audit_logs(entity_type: str, entity_id: str):
    """Get audit logs for a specific entity"""
    if not database.connected or database.audit_logs is None:
        return []

    logs = list(database.audit_logs.find({
        "entity_type": entity_type,
        "entity_id": entity_id
    }).sort("created_at", -1))
    return serialize_docs(logs)


# ============ Projects ============

@router.get("/projects")
async def get_projects():
    """Get all projects"""
    if not database.connected or database.projects is None:
        return []

    projects = list(database.projects.find().sort("name", 1))
    return serialize_docs(projects)


@router.post("/projects")
async def create_project(data: ProjectCreate):
    """Create a new project"""
    if not database.connected or database.projects is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    result = database.projects.insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    log_action("create", "project", str(result.inserted_id), data.name)
    return doc


@router.put("/projects/{project_id}")
async def update_project(project_id: str, data: ProjectCreate):
    """Update a project"""
    if not database.connected or database.projects is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    result = database.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")

    log_action("update", "project", project_id, data.name)
    return {"status": "updated"}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project"""
    if not database.connected or database.projects is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    project = database.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    database.products.update_many(
        {"project_id": project_id},
        {"$unset": {"project_id": ""}}
    )

    database.projects.delete_one({"_id": ObjectId(project_id)})
    log_action("delete", "project", project_id, project.get("name", ""))
    return {"status": "deleted"}
