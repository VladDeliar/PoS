"""
Geocoding utility for Ukrainian addresses using Google Maps API.

This module provides backend-proxied geocoding to:
1. Keep Google API key secure (never exposed in frontend)
2. Apply Ukrainian address formatting (locality, language, region biasing)
3. Handle errors gracefully
"""

import aiohttp
from typing import Optional, Tuple
from ..config import GOOGLE_MAPS_API_KEY

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def geocode_address(
    address: str,
    locality: str = "Івано-Франківськ"
) -> Optional[Tuple[float, float]]:
    """
    Geocode a Ukrainian address using Google Maps API.

    Args:
        address: Street address (e.g., "Незалежності 36")
        locality: City name for context (default: Ivano-Frankivsk)

    Returns:
        Tuple of (lat, lng) or None if geocoding fails.

    Note:
        Always includes locality and country to ensure accurate results
        for Ukrainian addresses. Uses Ukrainian language for response.
    """
    if not GOOGLE_MAPS_API_KEY:
        return None

    params = {
        "address": f"{address}, {locality}, Україна",
        "key": GOOGLE_MAPS_API_KEY,
        "language": "uk",
        "region": "ua",
        "components": f"country:UA|locality:{locality}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GEOCODING_URL, params=params) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()

                if data.get("status") != "OK" or not data.get("results"):
                    return None

                location = data["results"][0]["geometry"]["location"]
                return (location["lat"], location["lng"])
    except Exception:
        return None
