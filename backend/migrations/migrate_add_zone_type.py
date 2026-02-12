"""
Migration: Add zone_type field to existing delivery zones.

This migration adds the zone_type field to all existing delivery zones,
setting them to "radius" (the current behavior).

Usage:
    python -m backend.migrations.migrate_add_zone_type
"""

import asyncio
from datetime import datetime
import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend import database


async def migrate_existing_zones():
    """Add zone_type field to existing zones without it."""
    print("Starting migration: Add zone_type to delivery zones...")

    # Wait for database connection
    if not database.connected:
        print("Waiting for database connection...")
        await asyncio.sleep(2)

    if not database.connected or database.delivery_zones is None:
        print("ERROR: Database not available")
        return False

    # Find zones without zone_type field
    zones_without_type = database.delivery_zones.find({"zone_type": {"$exists": False}})
    count = database.delivery_zones.count_documents({"zone_type": {"$exists": False}})

    if count == 0:
        print("No zones need migration. All zones already have zone_type field.")
        return True

    print(f"Found {count} zones without zone_type field.")
    print("Setting zone_type='radius' for all existing zones...")

    # Update all zones without zone_type to "radius"
    result = database.delivery_zones.update_many(
        {"zone_type": {"$exists": False}},
        {
            "$set": {
                "zone_type": "radius",
                "updated_at": datetime.utcnow()
            }
        }
    )

    print(f"✓ Migration completed successfully!")
    print(f"  - Updated {result.modified_count} zones")
    print(f"  - All existing zones now have zone_type='radius'")

    return True


async def main():
    """Run migration."""
    print("=" * 60)
    print("Delivery Zones Migration")
    print("=" * 60)

    success = await migrate_existing_zones()

    if success:
        print("\n✓ Migration completed successfully!")
    else:
        print("\n✗ Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
