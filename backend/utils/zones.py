"""
Zone geometry and detection utilities.

This module handles:
1. Converting circular zones to GeoJSON polygons for MongoDB storage
2. Detecting which zone a coordinate falls within using geospatial queries

CRITICAL: Coordinate order matters!
- GeoJSON uses [longitude, latitude] (lng first)
- Leaflet uses [latitude, longitude] (lat first)
Always convert explicitly when crossing boundaries.
"""

import math
from typing import List, Optional
from .. import database


def circle_to_polygon(
    center_lat: float,
    center_lng: float,
    radius_km: float,
    num_points: int = 64
) -> List[List[float]]:
    """
    Convert a circle to GeoJSON Polygon coordinates.

    Creates a polygon approximation of a circle using the specified number
    of points. This enables MongoDB $geoIntersects queries.

    Args:
        center_lat: Latitude of circle center
        center_lng: Longitude of circle center
        radius_km: Radius in kilometers
        num_points: Number of points for polygon approximation (default: 64)

    Returns:
        GeoJSON coordinates: [[[lng, lat], [lng, lat], ...]]
        Note: Returns nested list for GeoJSON Polygon format.
        Note: Coordinates are [lng, lat] order (GeoJSON standard).

    Example:
        >>> coords = circle_to_polygon(48.9219, 24.7082, 2.0)
        >>> len(coords[0])  # 65 points (64 + closing point)
        65
    """
    coords = []
    earth_radius_km = 6371

    # Pre-calculate invariants outside the loop
    cos_lat = math.cos(math.radians(center_lat))
    lat_factor = (radius_km / earth_radius_km) * math.degrees(1)
    lng_factor = lat_factor / cos_lat

    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        delta_lat = lat_factor * math.cos(angle)
        delta_lng = lng_factor * math.sin(angle)

        # GeoJSON order: [lng, lat]
        coords.append([center_lng + delta_lng, center_lat + delta_lat])

    # Close the polygon (first point == last point)
    coords.append(coords[0])

    # GeoJSON Polygon requires nested array
    return [coords]


def detect_zone(lat: float, lng: float) -> Optional[dict]:
    """
    Find the delivery zone containing the given coordinates.

    Uses MongoDB $geoIntersects query to find all enabled zones
    containing the point, then returns the highest priority zone
    (lowest priority number).

    Args:
        lat: Latitude of the point to check
        lng: Longitude of the point to check

    Returns:
        Zone document dict or None if outside all zones.

    Note:
        Priority resolution: If a point is in multiple overlapping zones,
        the zone with the lowest priority number wins (priority 1 beats 2).

    Note:
        Coordinate order: Input is (lat, lng) but internally converted
        to GeoJSON [lng, lat] for the query.
    """
    if not database.connected or database.delivery_zones is None:
        return None

    # GeoJSON Point: coordinates are [lng, lat]
    point = {
        "type": "Point",
        "coordinates": [lng, lat]  # GeoJSON order: [lng, lat]
    }

    # Find all enabled zones containing this point, sorted by priority
    # Lower priority number = higher precedence
    try:
        zones = list(database.delivery_zones.find({
            "enabled": True,
            "geometry": {
                "$geoIntersects": {
                    "$geometry": point
                }
            }
        }).sort("priority", 1).limit(1))

        return zones[0] if zones else None
    except Exception:
        return None


def calculate_polygon_centroid(geometry: dict) -> dict:
    """
    Calculate centroid of a GeoJSON Polygon.

    Simple average of coordinates - good enough for display purposes.
    For more accurate geographic centroid, consider using Shapely library.

    Args:
        geometry: GeoJSON Polygon geometry dict with type and coordinates

    Returns:
        Dict with "lat" and "lng" keys representing the centroid

    Raises:
        ValueError: If geometry is not a Polygon

    Example:
        >>> geom = {"type": "Polygon", "coordinates": [[[24.0, 48.0], [24.1, 48.0], [24.1, 48.1], [24.0, 48.1], [24.0, 48.0]]]}
        >>> centroid = calculate_polygon_centroid(geom)
        >>> centroid["lat"]  # approximately 48.05
        >>> centroid["lng"]  # approximately 24.05
    """
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise ValueError("Only Polygon geometry supported")

    coords = geometry.get("coordinates", [[]])
    if not coords or len(coords) < 1:
        raise ValueError("Polygon must have coordinates")

    # Get outer ring (first element)
    outer_ring = coords[0]

    if len(outer_ring) < 4:
        raise ValueError("Polygon must have at least 3 vertices")

    # Calculate average lat/lng
    # GeoJSON format: [lng, lat]
    total_lat = 0.0
    total_lng = 0.0
    count = len(outer_ring) - 1  # Exclude closing point (first == last)

    for coord in outer_ring[:-1]:  # Skip last point (same as first)
        lng, lat = coord[0], coord[1]
        total_lng += lng
        total_lat += lat

    return {
        "lat": total_lat / count,
        "lng": total_lng / count
    }
