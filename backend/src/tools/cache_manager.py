"""
Tool Cache Manager

Provides Redis-backed caching for tool execution results.
Different tools have different TTLs based on data freshness requirements.
"""

import logging
import json
import hashlib
from typing import Any, Optional, Dict
from datetime import timedelta
import redis.asyncio as aioredis

from src.core.config import settings

logger = logging.getLogger(__name__)


class ToolCacheManager:
    """
    Redis-backed cache for tool execution results.

    Features:
    - Per-tool TTL configuration
    - Cache hit/miss tracking
    - Automatic key generation from tool name + args

    Usage:
        cache = ToolCacheManager()
        await cache.connect()

        # Check cache
        result = await cache.get("arxiv_search", query="AI")
        if result:
            # Cache hit
            return result

        # Cache miss - execute and store
        result = await execute_tool(...)
        await cache.set("arxiv_search", result, query="AI")
    """

    # TTL configuration per tool (in seconds)
    TTL_CONFIG: Dict[str, int] = {
        "arxiv_search": 3600,           # 1 hour
        "arxiv_search_keywords": 3600,  # 1 hour
        "hf_trending": 1800,            # 30 minutes
        "collect_url": 86400,           # 24 hours
        "default": 3600,                # 1 hour
    }

    def __init__(self, redis_url: str = None):
        """Initialize cache manager."""
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis: Optional[aioredis.Redis] = None

        # Metrics
        self._cache_hits = 0
        self._cache_misses = 0

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Connected to Redis for tool cache")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Cache disabled.")
            self.redis = None

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()

    def _generate_cache_key(self, tool_name: str, **kwargs) -> str:
        """
        Generate a unique cache key from tool name and arguments.

        Args:
            tool_name: Name of the tool
            **kwargs: Tool arguments

        Returns:
            Cache key string
        """
        # Sort kwargs for consistent hashing
        sorted_args = json.dumps(kwargs, sort_keys=True)
        args_hash = hashlib.md5(sorted_args.encode()).hexdigest()
        return f"tool_cache:{tool_name}:{args_hash}"

    async def get(self, tool_name: str, **kwargs) -> Optional[Any]:
        """
        Get cached result for tool execution.

        Args:
            tool_name: Name of the tool
            **kwargs: Tool arguments

        Returns:
            Cached result or None if not found
        """
        if not self.redis:
            return None

        try:
            key = self._generate_cache_key(tool_name, **kwargs)
            cached = await self.redis.get(key)

            if cached:
                self._cache_hits += 1
                logger.debug(f"Cache HIT for {tool_name}")
                return json.loads(cached)
            else:
                self._cache_misses += 1
                logger.debug(f"Cache MISS for {tool_name}")
                return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, tool_name: str, result: Any, **kwargs):
        """
        Store tool execution result in cache.

        Args:
            tool_name: Name of the tool
            result: Result to cache
            **kwargs: Tool arguments (for key generation)
        """
        if not self.redis:
            return

        try:
            key = self._generate_cache_key(tool_name, **kwargs)
            ttl = self.TTL_CONFIG.get(tool_name, self.TTL_CONFIG["default"])

            # Serialize result
            serialized = json.dumps(result)

            # Store with TTL
            await self.redis.setex(key, ttl, serialized)
            logger.debug(f"Cached result for {tool_name} (TTL: {ttl}s)")

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def invalidate(self, tool_name: str, **kwargs):
        """Invalidate cached result."""
        if not self.redis:
            return

        try:
            key = self._generate_cache_key(tool_name, **kwargs)
            await self.redis.delete(key)
            logger.debug(f"Invalidated cache for {tool_name}")
        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")

    async def clear_all(self):
        """Clear all tool cache entries."""
        if not self.redis:
            return

        try:
            keys = await self.redis.keys("tool_cache:*")
            if keys:
                await self.redis.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries")
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._cache_hits + self._cache_misses
        if total == 0:
            return 0.0
        return self._cache_hits / total

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics."""
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
        }

    def reset_metrics(self):
        """Reset cache metrics."""
        self._cache_hits = 0
        self._cache_misses = 0


# Global cache instance
_cache_manager: Optional[ToolCacheManager] = None


async def get_cache_manager() -> ToolCacheManager:
    """Get or create global cache manager."""
    global _cache_manager

    if _cache_manager is None:
        _cache_manager = ToolCacheManager()
        await _cache_manager.connect()

    return _cache_manager


async def close_cache_manager():
    """Close global cache manager."""
    global _cache_manager

    if _cache_manager:
        await _cache_manager.close()
        _cache_manager = None
