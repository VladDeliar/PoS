"""
Migration: Convert storefront config from v1 to v2 (PageBuilder) format.

This migration reads the existing storefront configuration from app_settings
and converts it from the old block-based v1 format to the new section-based
v2 PageBuilder format. The original v1 data is preserved in a backup field.

Usage:
    python -m backend.migrations.migrate_storefront_v2
"""

import sys
import os
from uuid import uuid4

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend import database


def _uid():
    return str(uuid4())[:8]


def migrate_v1_to_v2(old: dict) -> dict:
    """Convert old StorefrontConfig (v1) to PageBuilderConfig (v2).

    Duplicated from backend.routers.settings to keep migration self-contained.
    """
    sections = []
    blocks = sorted(old.get("blocks", []), key=lambda b: b.get("sort_order", 0))

    announcement_data = old.get("announcement", {})
    hero_data = old.get("heroBanner", {})
    components = old.get("components", {})
    store_info = old.get("storeInfo", {})

    for block in blocks:
        block_id = block.get("id", "")
        el_settings = {}
        el_type = block_id

        if block_id == "announcement":
            el_settings = {
                "text": announcement_data.get("text", ""),
                "bgColor": announcement_data.get("bgColor", "#FFF3E0"),
                "textColor": announcement_data.get("textColor", "#E65100"),
            }
        elif block_id == "hero_banner":
            el_type = "image"
            el_settings = {
                "imageUrl": hero_data.get("imageUrl", ""),
                "altText": hero_data.get("altText", ""),
                "linkUrl": hero_data.get("linkUrl", ""),
                "width": "100%",
                "borderRadius": "8px",
            }
        elif block_id == "menu":
            el_settings = {
                "productViewMode": components.get("productViewMode", "list"),
                "navPosition": components.get("navPosition", "sidebar"),
                "cardStyle": components.get("cardStyle", "default"),
            }
        elif block_id == "hours":
            el_settings = {"showIcon": True}
        elif block_id == "address":
            el_settings = {
                "showMap": bool(store_info.get("googleMapsEmbedUrl")),
                "showCopyButton": store_info.get("showCopyButtons", True),
            }
        elif block_id == "phone":
            el_settings = {
                "showCopyButton": store_info.get("showCopyButtons", True),
            }

        section = {
            "id": _uid(),
            "label": block.get("label", block_id),
            "collapsed": False,
            "visible": block.get("enabled", True),
            "sort_order": block.get("sort_order", 0),
            "settings": {},
            "rows": [{
                "id": _uid(),
                "visible": True,
                "sort_order": 0,
                "settings": {},
                "columns": [{
                    "id": _uid(),
                    "width": "1/1",
                    "sort_order": 0,
                    "settings": {},
                    "elements": [{
                        "id": _uid(),
                        "type": el_type,
                        "label": block.get("label", ""),
                        "visible": True,
                        "sort_order": 0,
                        "settings": el_settings,
                    }],
                }],
            }],
        }
        sections.append(section)

    # If store_info has googleMapsEmbedUrl, add a map section
    maps_url = store_info.get("googleMapsEmbedUrl", "")
    if maps_url:
        has_map = any(
            s["rows"][0]["columns"][0]["elements"][0]["type"] == "map"
            for s in sections
            if s.get("rows") and s["rows"][0].get("columns")
            and s["rows"][0]["columns"][0].get("elements")
        )
        if not has_map:
            sections.append({
                "id": _uid(),
                "label": "Map",
                "collapsed": False,
                "visible": True,
                "sort_order": len(sections),
                "settings": {},
                "rows": [{
                    "id": _uid(),
                    "visible": True,
                    "sort_order": 0,
                    "settings": {},
                    "columns": [{
                        "id": _uid(),
                        "width": "1/1",
                        "sort_order": 0,
                        "settings": {},
                        "elements": [{
                            "id": _uid(),
                            "type": "map",
                            "label": "Google Map",
                            "visible": True,
                            "sort_order": 0,
                            "settings": {
                                "googleMapsEmbedUrl": maps_url,
                                "height": "300px",
                            },
                        }],
                    }],
                }],
            })

    return {
        "version": 2,
        "sections": sections,
        "branding": old.get("branding", {
            "accentColor": "#4CAF50",
            "fontFamily": "system",
            "borderRadius": "default",
        }),
        "globalSettings": {},
    }


def run_migration():
    """Migrate storefront config from v1 to v2 in the database."""
    print("Starting migration: Storefront v1 -> v2 (PageBuilder)...")

    database.connect_db()

    if not database.connected or database.settings is None:
        print("ERROR: Database not available. Check MONGODB_URL in .env")
        return False

    doc = database.settings.find_one({"_id": "app_settings"})
    if not doc:
        print("No app_settings document found. Nothing to migrate.")
        return True

    storefront = doc.get("storefront")
    if not storefront:
        print("No storefront config found in app_settings. Nothing to migrate.")
        return True

    if storefront.get("version") == 2:
        print("Storefront config is already v2. No migration needed.")
        return True

    print(f"Found v1 storefront config with {len(storefront.get('blocks', []))} blocks.")
    print("Converting to v2 PageBuilder format...")

    v2_config = migrate_v1_to_v2(storefront)

    print(f"  - Created {len(v2_config['sections'])} sections")
    for section in v2_config["sections"]:
        el = section["rows"][0]["columns"][0]["elements"][0]
        vis = "visible" if section["visible"] else "hidden"
        print(f"    [{vis}] {section['label']} ({el['type']})")

    # Backup v1 config and write v2
    database.settings.update_one(
        {"_id": "app_settings"},
        {"$set": {
            "storefront": v2_config,
            "storefront_v1_backup": storefront,
        }}
    )

    print("\nMigration applied successfully!")
    print("  - v2 config saved to storefront field")
    print("  - v1 config backed up to storefront_v1_backup field")
    return True


def rollback():
    """Rollback: restore v1 config from backup."""
    print("Rolling back storefront v2 migration...")

    database.connect_db()

    if not database.connected or database.settings is None:
        print("ERROR: Database not available.")
        return False

    doc = database.settings.find_one({"_id": "app_settings"})
    if not doc or not doc.get("storefront_v1_backup"):
        print("No v1 backup found. Cannot rollback.")
        return False

    database.settings.update_one(
        {"_id": "app_settings"},
        {
            "$set": {"storefront": doc["storefront_v1_backup"]},
            "$unset": {"storefront_v1_backup": ""},
        }
    )

    print("Rollback complete. v1 config restored.")
    return True


def main():
    print("=" * 60)
    print("Storefront V2 (PageBuilder) Migration")
    print("=" * 60)

    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        success = rollback()
    else:
        success = run_migration()

    database.close_db()

    if success:
        print("\nDone!")
    else:
        print("\nFailed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
