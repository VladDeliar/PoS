from datetime import datetime

from fastapi import APIRouter, HTTPException

from .. import database
from ..models import FeedbackCreate
from ..utils.serializers import serialize_docs
from ..utils.demo_data import DEMO_FEEDBACKS

router = APIRouter(prefix="/api/feedbacks", tags=["feedbacks"])


@router.get("/")
async def get_feedbacks(limit: int = 50):
    """Get all feedbacks (for admin view)"""
    if not database.connected or database.feedbacks is None:
        return DEMO_FEEDBACKS[:limit]
    return serialize_docs(
        database.feedbacks.find().sort("created_at", -1).limit(limit)
    )


@router.post("/")
async def create_feedback(data: FeedbackCreate):
    """Create a new feedback/review"""
    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    feedback_doc = {
        "rating": data.rating,
        "phone": data.phone,
        "comment": data.comment,
        "created_at": datetime.utcnow()
    }

    if not database.connected or database.feedbacks is None:
        feedback_doc["_id"] = str(len(DEMO_FEEDBACKS) + 1)
        feedback_doc["created_at"] = feedback_doc["created_at"].isoformat()
        DEMO_FEEDBACKS.insert(0, feedback_doc)
    else:
        result = database.feedbacks.insert_one(feedback_doc)
        feedback_doc["_id"] = str(result.inserted_id)
        feedback_doc["created_at"] = feedback_doc["created_at"].isoformat()

    return feedback_doc


@router.get("/stats")
async def get_feedback_stats():
    """Get feedback statistics"""
    if not database.connected or database.feedbacks is None:
        if not DEMO_FEEDBACKS:
            return {"total": 0, "average_rating": 0, "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}}
        total = len(DEMO_FEEDBACKS)
        avg = sum(f["rating"] for f in DEMO_FEEDBACKS) / total
        dist = {i: len([f for f in DEMO_FEEDBACKS if f["rating"] == i]) for i in range(1, 6)}
        return {"total": total, "average_rating": round(avg, 1), "rating_distribution": dist}

    pipeline = [
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "average_rating": {"$avg": "$rating"}
        }}
    ]
    result = list(database.feedbacks.aggregate(pipeline))

    if not result:
        return {"total": 0, "average_rating": 0, "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}}

    dist_pipeline = [
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}}
    ]
    dist_result = list(database.feedbacks.aggregate(dist_pipeline))
    distribution = {i: 0 for i in range(1, 6)}
    for item in dist_result:
        distribution[item["_id"]] = item["count"]

    return {
        "total": result[0]["total"],
        "average_rating": round(result[0]["average_rating"], 1),
        "rating_distribution": distribution
    }
