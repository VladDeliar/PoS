import json
import logging
from typing import Any, Optional
import redis.asyncio as redis
from .config import REDIS_URL, REDIS_CHANNELS

logger = logging.getLogger(__name__)


class RedisManager:
    def __init__(self):
        self.redis: redis.Redis = None
        self.pubsub: redis.client.PubSub = None

    async def connect(self):
        """Connect to Redis Cloud"""
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)
        await self.redis.ping()
        logger.info("Connected to Redis")

    async def close(self):
        """Close Redis connection"""
        if self.pubsub:
            await self.pubsub.aclose()
        if self.redis:
            await self.redis.aclose()
        logger.info("Redis connection closed")

    async def publish(self, channel: str, message: dict):
        """Publish message to channel"""
        await self.redis.publish(channel, json.dumps(message, default=str))

    async def subscribe(self, channels: list = None) -> redis.client.PubSub:
        """Subscribe to channels and return pubsub instance"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(*(channels or REDIS_CHANNELS))
        return pubsub

    # ============ Caching Methods ============

    async def get_cached(self, key: str) -> Optional[Any]:
        """Get cached data by key"""
        if not self.redis:
            return None
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def set_cached(self, key: str, data: Any, ttl: int = 3600):
        """Cache data with TTL in seconds (default 1 hour)"""
        if not self.redis:
            return
        try:
            await self.redis.set(key, json.dumps(data, default=str), ex=ttl)
        except Exception:
            pass

    async def invalidate(self, pattern: str):
        """Invalidate cache keys matching pattern"""
        if not self.redis:
            return
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self.redis.delete(*keys)
        except Exception:
            pass

    async def invalidate_key(self, key: str):
        """Invalidate a specific cache key"""
        if not self.redis:
            return
        try:
            await self.redis.delete(key)
        except Exception:
            pass


# Cache key constants
CACHE_CATEGORIES = "cache:categories"
CACHE_PRODUCT_TAGS = "cache:product_tags"
CACHE_DELIVERY_ZONES = "cache:delivery_zones"
CACHE_MODIFIERS = "cache:modifiers"
CACHE_MENU_ITEMS = "cache:menu_items"

# TTL values in seconds
TTL_CATEGORIES = 3600       # 1 hour
TTL_PRODUCT_TAGS = 7200     # 2 hours
TTL_DELIVERY_ZONES = 1800   # 30 minutes
TTL_MODIFIERS = 7200        # 2 hours
TTL_MENU_ITEMS = 900        # 15 minutes

redis_manager = RedisManager()
