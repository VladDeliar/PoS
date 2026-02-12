from datetime import datetime
from bson import ObjectId


def serialize_doc(doc):
    """Convert MongoDB document to dict with string _id"""
    if doc:
        doc["_id"] = str(doc["_id"])
        if "category_id" in doc and doc["category_id"]:
            doc["category_id"] = str(doc["category_id"])
        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
    return doc


def serialize_docs(docs):
    """Convert list of MongoDB documents"""
    return [serialize_doc(doc) for doc in docs]


def serialize_all(obj):
    """Recursively convert all ObjectId to strings"""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: serialize_all(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_all(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj
