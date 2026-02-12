"""
Delivery Zones API Router.

Provides CRUD operations for delivery zones and zone detection endpoints.
Supports demo mode fallback when database is not connected.
"""

from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from pymongo import ReturnDocument, UpdateOne

from .. import database
from ..models import (
    DeliveryZone,
    DeliveryZoneCreate,
    DeliveryCenterUpdate,
    GeocodeRequest,
    ZoneDetectionResult,
    ZoneType
)
from ..utils.serializers import serialize_doc
from ..utils.demo_data import DEMO_ZONES, DEMO_CENTER
from ..utils.geocoding import geocode_address
from ..utils.zones import circle_to_polygon, detect_zone, calculate_polygon_centroid
from ..redis_manager import redis_manager, CACHE_DELIVERY_ZONES, TTL_DELIVERY_ZONES

router = APIRouter(prefix="/api/delivery-zones", tags=["delivery-zones"])


def _get_center() -> dict:
    """Get delivery center from database or demo data."""
    if not database.connected or database.settings is None:
        return DEMO_CENTER

    center = database.settings.find_one({"_id": "delivery_center"})
    if center:
        return {
            "lat": center.get("lat", DEMO_CENTER["lat"]),
            "lng": center.get("lng", DEMO_CENTER["lng"]),
            "address": center.get("address", "")
        }
    return DEMO_CENTER


def _build_zone_geometry(zone_data: dict, center: dict) -> dict:
    """
    Build GeoJSON geometry based on zone type.

    For radius zones: Convert circle to polygon using center and radius.
    For polygon zones: Return user-drawn geometry as-is.
    """
    zone_type = zone_data.get("zone_type", "radius")

    if zone_type == "radius" or zone_type == ZoneType.RADIUS:
        # Use zone's custom center if provided, otherwise use delivery center
        center_lat = zone_data.get("center_lat", center["lat"])
        center_lng = zone_data.get("center_lng", center["lng"])

        coords = circle_to_polygon(
            center_lat=center_lat,
            center_lng=center_lng,
            radius_km=zone_data["radius_km"]
        )
        return {
            "type": "Polygon",
            "coordinates": coords
        }
    elif zone_type == "polygon" or zone_type == ZoneType.POLYGON:
        # Return custom geometry directly
        return zone_data["custom_geometry"]
    else:
        raise ValueError(f"Unknown zone_type: {zone_type}")


def _prepare_zone_data(zone: DeliveryZoneCreate, center: dict) -> dict:
    """Prepare zone data dict with geometry based on zone type."""
    zone_data = zone.model_dump()

    if zone.zone_type == ZoneType.RADIUS:
        if zone.center_lat is None or zone.center_lng is None:
            zone_data["center_lat"] = center["lat"]
            zone_data["center_lng"] = center["lng"]
        zone_data["geometry"] = _build_zone_geometry(zone_data, center)

    elif zone.zone_type == ZoneType.POLYGON:
        zone_data["geometry"] = zone.custom_geometry
        try:
            centroid = calculate_polygon_centroid(zone.custom_geometry)
            zone_data["center_lat"] = centroid["lat"]
            zone_data["center_lng"] = centroid["lng"]
        except Exception:
            zone_data["center_lat"] = None
            zone_data["center_lng"] = None

    return zone_data


# ============== Zone CRUD ==============

@router.get("/")
async def list_zones() -> List[dict]:
    """List all delivery zones sorted by priority."""
    # Try cache first
    cached = await redis_manager.get_cached(CACHE_DELIVERY_ZONES)
    if cached is not None:
        return cached

    if not database.connected or database.delivery_zones is None:
        return DEMO_ZONES

    zones = list(database.delivery_zones.find().sort("priority", 1))
    result = [serialize_doc(z) for z in zones]

    # Cache the result
    await redis_manager.set_cached(CACHE_DELIVERY_ZONES, result, TTL_DELIVERY_ZONES)
    return result


@router.get("/{zone_id}")
async def get_zone(zone_id: str) -> dict:
    """Get a single delivery zone by ID."""
    if not database.connected or database.delivery_zones is None:
        for zone in DEMO_ZONES:
            if zone["_id"] == zone_id:
                return zone
        raise HTTPException(status_code=404, detail="Zone not found")

    if not ObjectId.is_valid(zone_id):
        raise HTTPException(status_code=400, detail="Invalid zone ID")

    zone = database.delivery_zones.find_one({"_id": ObjectId(zone_id)})
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    return serialize_doc(zone)


@router.post("/")
async def create_zone(zone: DeliveryZoneCreate) -> dict:
    """Create a new delivery zone (radius or polygon type)."""
    if not database.connected or database.delivery_zones is None:
        raise HTTPException(status_code=503, detail="Database not available")

    center = _get_center()
    zone_data = _prepare_zone_data(zone, center)

    zone_data["created_at"] = datetime.utcnow()
    zone_data["updated_at"] = datetime.utcnow()

    result = database.delivery_zones.insert_one(zone_data)
    zone_data["_id"] = result.inserted_id

    await redis_manager.invalidate_key(CACHE_DELIVERY_ZONES)

    return serialize_doc(zone_data)


@router.put("/{zone_id}")
async def update_zone(zone_id: str, zone: DeliveryZoneCreate) -> dict:
    """Update an existing delivery zone (radius or polygon type)."""
    if not database.connected or database.delivery_zones is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(zone_id):
        raise HTTPException(status_code=400, detail="Invalid zone ID")

    existing = database.delivery_zones.find_one({"_id": ObjectId(zone_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Zone not found")

    center = _get_center()
    zone_data = _prepare_zone_data(zone, center)
    zone_data["updated_at"] = datetime.utcnow()

    updated = database.delivery_zones.find_one_and_update(
        {"_id": ObjectId(zone_id)},
        {"$set": zone_data},
        return_document=ReturnDocument.AFTER
    )

    await redis_manager.invalidate_key(CACHE_DELIVERY_ZONES)

    return serialize_doc(updated)


@router.delete("/{zone_id}")
async def delete_zone(zone_id: str) -> dict:
    """Delete a delivery zone."""
    if not database.connected or database.delivery_zones is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not ObjectId.is_valid(zone_id):
        raise HTTPException(status_code=400, detail="Invalid zone ID")

    result = database.delivery_zones.delete_one({"_id": ObjectId(zone_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Zone not found")

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_DELIVERY_ZONES)

    return {"status": "deleted", "zone_id": zone_id}


# ============== Center Point ==============

@router.get("/center/info")
async def get_center() -> dict:
    """Get the delivery center point."""
    return _get_center()


@router.put("/center/info")
async def update_center(center: DeliveryCenterUpdate) -> dict:
    """
    Update the delivery center point.

    Note: Changing the center requires recalculating geometry for ALL zones.
    This is done lazily - zones will be updated on next individual zone update,
    or you can trigger a bulk update by calling POST /recalculate-all.
    """
    if not database.connected or database.settings is None:
        raise HTTPException(status_code=503, detail="Database not available")

    center_data = {
        "_id": "delivery_center",
        "lat": center.lat,
        "lng": center.lng,
        "address": center.address
    }

    database.settings.update_one(
        {"_id": "delivery_center"},
        {"$set": center_data},
        upsert=True
    )

    # Invalidate zones cache since center changed
    await redis_manager.invalidate_key(CACHE_DELIVERY_ZONES)

    return {
        "lat": center.lat,
        "lng": center.lng,
        "address": center.address
    }


@router.post("/recalculate-all")
async def recalculate_all_zones() -> dict:
    """
    Recalculate geometry for RADIUS zones only based on current center.

    Polygon zones are not affected by center changes.
    Use this after updating the center point to update radius zone geometries.
    """
    if not database.connected or database.delivery_zones is None:
        raise HTTPException(status_code=503, detail="Database not available")

    center = _get_center()

    # Only get radius zones - polygon zones are not affected by center changes
    zones = list(database.delivery_zones.find({"zone_type": "radius"}))

    if not zones:
        return {
            "status": "recalculated",
            "zones_updated": 0,
            "message": "No radius zones to recalculate. Polygon zones are not affected by center changes."
        }

    # Optimized: use bulk_write instead of N separate update calls
    now = datetime.utcnow()
    operations = [
        UpdateOne(
            {"_id": zone["_id"]},
            {"$set": {"geometry": _build_zone_geometry(zone, center), "updated_at": now}}
        )
        for zone in zones
    ]

    result = database.delivery_zones.bulk_write(operations)

    # Invalidate cache
    await redis_manager.invalidate_key(CACHE_DELIVERY_ZONES)

    return {
        "status": "recalculated",
        "zones_updated": result.modified_count,
        "message": "Only radius zones were recalculated. Polygon zones unchanged."
    }


# ============== Zone Detection ==============

@router.post("/detect")
async def detect_zone_from_address(request: GeocodeRequest) -> ZoneDetectionResult:
    """
    Detect delivery zone from a Ukrainian address.

    1. Geocodes the address using Google Maps API
    2. Finds the zone containing the coordinates
    3. Returns zone details or "unavailable" message
    """
    # Demo mode - return unavailable
    if not database.connected:
        return ZoneDetectionResult(
            available=False,
            message="Сервіс геокодування недоступний у демо-режимі"
        )

    # Geocode the address
    coords = await geocode_address(request.address)
    if coords is None:
        return ZoneDetectionResult(
            available=False,
            message="Не вдалося визначити адресу. Перевірте правильність написання."
        )

    lat, lng = coords

    # Detect zone
    zone = detect_zone(lat, lng)

    if zone is None:
        return ZoneDetectionResult(
            available=False,
            coordinates={"lat": lat, "lng": lng},
            message="На жаль, доставка за цією адресою недоступна"
        )

    return ZoneDetectionResult(
        zone_id=str(zone.get("_id", "")),
        zone_name=zone.get("name", ""),
        delivery_fee=zone.get("delivery_fee", 0),
        min_order_amount=zone.get("min_order_amount", 0),
        free_delivery_threshold=zone.get("free_delivery_threshold"),
        coordinates={"lat": lat, "lng": lng},
        available=True,
        message=f"Доставка: {zone.get('name', '')}"
    )


@router.post("/detect-coordinates")
async def detect_zone_from_coordinates(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180)
) -> ZoneDetectionResult:
    """
    Detect delivery zone from coordinates (for testing).

    Skips geocoding - useful for admin testing with known coordinates.
    """
    # Demo mode
    if not database.connected:
        return ZoneDetectionResult(
            available=False,
            coordinates={"lat": lat, "lng": lng},
            message="Визначення зони недоступне у демо-режимі"
        )

    zone = detect_zone(lat, lng)

    if zone is None:
        return ZoneDetectionResult(
            available=False,
            coordinates={"lat": lat, "lng": lng},
            message="Координати знаходяться поза зонами доставки"
        )

    return ZoneDetectionResult(
        zone_id=str(zone.get("_id", "")),
        zone_name=zone.get("name", ""),
        delivery_fee=zone.get("delivery_fee", 0),
        min_order_amount=zone.get("min_order_amount", 0),
        free_delivery_threshold=zone.get("free_delivery_threshold"),
        coordinates={"lat": lat, "lng": lng},
        available=True,
        message=f"Зона: {zone.get('name', '')}"
    )
