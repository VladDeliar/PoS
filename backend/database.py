import logging
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.database import Database
from pymongo.collection import Collection
from .config import MONGODB_URL, MONGODB_DB_NAME

logger = logging.getLogger(__name__)

client: MongoClient = None
db: Database = None
connected: bool = False

# Collections
products: Collection = None
orders: Collection = None
categories: Collection = None
settings: Collection = None
feedbacks: Collection = None
promo_codes: Collection = None
modifiers: Collection = None
combos: Collection = None
menu_items: Collection = None
product_tags: Collection = None
audit_logs: Collection = None
projects: Collection = None
delivery_zones: Collection = None
branches: Collection = None
customers: Collection = None
customer_categories: Collection = None
site_pages: Collection = None


def connect_db():
    """Connect to MongoDB Atlas"""
    global client, db, products, orders, categories, settings, feedbacks, promo_codes, modifiers, combos, menu_items, product_tags, audit_logs, projects, delivery_zones, branches, customers, customer_categories, site_pages, connected

    try:
        client = MongoClient(MONGODB_URL, server_api=ServerApi('1'))
        db = client[MONGODB_DB_NAME]

        products = db["products"]
        orders = db["orders"]
        categories = db["categories"]
        settings = db["settings"]
        feedbacks = db["feedbacks"]
        promo_codes = db["promo_codes"]
        modifiers = db["modifiers"]
        combos = db["combos"]
        menu_items = db["menu_items"]
        product_tags = db["product_tags"]
        audit_logs = db["audit_logs"]
        projects = db["projects"]
        delivery_zones = db["delivery_zones"]
        branches = db["branches"]
        customers = db["customers"]
        customer_categories = db["customer_categories"]
        site_pages = db["site_pages"]

        # Create indexes
        products.create_index("category_id")
        products.create_index("available")
        products.create_index("tags")
        products.create_index("is_alcohol")
        products.create_index("project_id")
        orders.create_index("created_at")
        orders.create_index("status")
        categories.create_index("sort_order")
        feedbacks.create_index("created_at")
        promo_codes.create_index("code", unique=True)
        combos.create_index("available")
        menu_items.create_index("product_id")
        menu_items.create_index("is_active")
        menu_items.create_index("sort_order")
        product_tags.create_index("name", unique=True)
        audit_logs.create_index([("created_at", -1)])
        audit_logs.create_index("entity_type")
        projects.create_index("name")
        delivery_zones.create_index([("geometry", "2dsphere")])
        delivery_zones.create_index("enabled")
        delivery_zones.create_index("priority")
        branches.create_index("name")
        branches.create_index("is_active")
        customers.create_index("phone", unique=True)
        customers.create_index("category_ids")
        customers.create_index([("created_at", -1)])
        customers.create_index([("total_spent", -1)])
        customer_categories.create_index("name")
        customer_categories.create_index("is_active")
        site_pages.create_index("sort_order")
        site_pages.create_index("is_published")
        site_pages.create_index([("sort_order", 1), ("is_published", 1)])

        orders.create_index("order_type")
        orders.create_index("payment_status")

        # Compound indexes for common query patterns
        orders.create_index([("status", 1), ("created_at", -1)])
        orders.create_index([("order_type", 1), ("created_at", -1)])
        products.create_index([("category_id", 1), ("available", 1)])
        menu_items.create_index([("item_type", 1), ("combo_id", 1)])
        menu_items.create_index([("item_type", 1), ("product_id", 1)])
        audit_logs.create_index([("entity_type", 1), ("entity_id", 1)])
        promo_codes.create_index([("is_active", 1), ("valid_from", 1), ("valid_to", 1)])

        # Test connection
        client.admin.command('ping')
        connected = True
        logger.info("Connected to MongoDB: %s", MONGODB_DB_NAME)
    except Exception as e:
        connected = False
        logger.error("MongoDB connection failed: %s", e, exc_info=True)
        logger.info("Running in demo mode without database")


def close_db():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")


def get_db() -> Database:
    """Get database instance"""
    return db
