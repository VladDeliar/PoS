from fastapi import APIRouter, HTTPException
from bson import ObjectId

from .. import database
from ..models import ProjectCreate
from ..utils.serializers import serialize_doc

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/")
async def get_projects():
    if not database.connected or database.projects is None:
        return []
    return [serialize_doc(doc) for doc in database.projects.find().sort("sort_order", 1)]


@router.post("/")
async def create_project(data: ProjectCreate):
    if not database.connected or database.projects is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = database.projects.insert_one(data.model_dump())
    return {"_id": str(result.inserted_id), **data.model_dump()}


@router.put("/{project_id}")
async def update_project(project_id: str, data: ProjectCreate):
    if not database.connected or database.projects is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = database.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "updated"}


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    if not database.connected or database.projects is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    # Block deletion if any categories reference this project
    cat_count = database.categories.count_documents({"project_id": project_id})
    if cat_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Неможливо видалити проєкт: він містить {cat_count} категорі(й). Спочатку видаліть або перенесіть категорії."
        )

    result = database.projects.delete_one({"_id": ObjectId(project_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")

    return {"status": "deleted"}
