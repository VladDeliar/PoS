import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB Atlas (required)
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    raise ValueError("MONGODB_URL environment variable is required. Set it in .env file.")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "pos_clover")

# Redis Cloud (required)
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is required. Set it in .env file.")

# Redis Pub/Sub channels
CHANNEL_ORDERS_NEW = "pos:orders:new"
CHANNEL_STATS_UPDATE = "pos:stats:update"
REDIS_CHANNELS = [CHANNEL_ORDERS_NEW, CHANNEL_STATS_UPDATE]

# Restaurant settings
RESTAURANT_NAME = "PoS"
RESTAURANT_ADDRESS = "Івано-Франківськ"
RESTAURANT_PHONE = "+38069696969"
RESTAURANT_HOURS = "08:00 - 21:00"

# Telegram Bot settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Google Maps API (for delivery zone geocoding)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
