"""
Cache Manager for LisPendens Agent

Provides caching functionality with Redis primary and in-memory fallback.
Supports TTL, automatic cleanup, and error handling.
"""

import json
import time
import logging
from typing import Any, Optional, Dict
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache only")

class CacheManager:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        
        # Initialize Redis if available and URL provided
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                logger.info("📦 Redis cache client initialized")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, falling back to memory cache")
        
        # Start cleanup task for memory cache
        asyncio.create_task(self._cleanup_memory_cache())

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache (Redis first, then memory fallback)
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        try:
            # Try Redis first
            if self.redis_client:
                try:
                    value = await self.redis_client.get(key)
                    if value:
                        return json.loads(value)
                except Exception as redis_error:
                    logger.warning(f"Redis get failed for key '{key}': {redis_error}")
            
            # Fallback to memory cache
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if entry['expires_at'] > time.time():
                    logger.debug(f"Memory cache hit for key: {key}")
                    return entry['value']
                else:
                    # Expired entry
                    del self.memory_cache[key]
                    logger.debug(f"Removed expired key from memory cache: {key}")
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for key '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """
        Set value in cache with TTL
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (default: 1 hour)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            json_value = json.dumps(value, default=str)  # default=str handles datetime objects
            
            # Try Redis first
            if self.redis_client:
                try:
                    await self.redis_client.setex(key, ttl_seconds, json_value)
                    logger.debug(f"Cached in Redis: {key} (TTL: {ttl_seconds}s)")
                    return True
                except Exception as redis_error:
                    logger.warning(f"Redis set failed for key '{key}': {redis_error}")
            
            # Fallback to memory cache
            self.memory_cache[key] = {
                'value': value,
                'expires_at': time.time() + ttl_seconds,
                'created_at': time.time()
            }
            logger.debug(f"Cached in memory: {key} (TTL: {ttl_seconds}s)")
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            success = False
            
            # Try Redis first
            if self.redis_client:
                try:
                    deleted = await self.redis_client.delete(key)
                    success = deleted > 0
                    if success:
                        logger.debug(f"Deleted from Redis: {key}")
                except Exception as redis_error:
                    logger.warning(f"Redis delete failed for key '{key}': {redis_error}")
            
            # Also remove from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
                logger.debug(f"Deleted from memory cache: {key}")
                success = True
            
            return success
            
        except Exception as e:
            logger.error(f"Cache delete error for key '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists and is not expired
        """
        try:
            # Check Redis first
            if self.redis_client:
                try:
                    exists = await self.redis_client.exists(key)
                    if exists:
                        return True
                except Exception as redis_error:
                    logger.warning(f"Redis exists check failed for key '{key}': {redis_error}")
            
            # Check memory cache
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if entry['expires_at'] > time.time():
                    return True
                else:
                    # Clean up expired entry
                    del self.memory_cache[key]
            
            return False
            
        except Exception as e:
            logger.error(f"Cache exists check error for key '{key}': {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        stats = {
            'memory_cache_size': len(self.memory_cache),
            'redis_connected': self.redis_client is not None
        }
        
        if self.redis_client:
            try:
                info = await self.redis_client.info('memory')
                stats['redis_memory_used'] = info.get('used_memory_human', 'unknown')
            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")
        
        # Count expired entries in memory cache
        now = time.time()
        expired_count = sum(1 for entry in self.memory_cache.values() 
                          if entry['expires_at'] <= now)
        stats['memory_cache_expired'] = expired_count
        
        return stats

    async def clear_all(self) -> bool:
        """
        Clear all cache entries (use with caution!)
        
        Returns:
            True if successful
        """
        try:
            success = True
            
            # Clear Redis (only our keys if possible)
            if self.redis_client:
                try:
                    # Note: This flushes the entire Redis DB, be careful in production
                    await self.redis_client.flushdb()
                    logger.info("Cleared Redis cache")
                except Exception as redis_error:
                    logger.error(f"Failed to clear Redis cache: {redis_error}")
                    success = False
            
            # Clear memory cache
            self.memory_cache.clear()
            logger.info("Cleared memory cache")
            
            return success
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    async def _cleanup_memory_cache(self):
        """Background task to clean up expired entries from memory cache"""
        while True:
            try:
                await asyncio.sleep(60)  # Clean every minute
                
                now = time.time()
                expired_keys = [
                    key for key, entry in self.memory_cache.items()
                    if entry['expires_at'] <= now
                ]
                
                for key in expired_keys:
                    del self.memory_cache[key]
                
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                    
            except Exception as e:
                logger.error(f"Memory cache cleanup error: {e}")

    async def close(self):
        """Close Redis connection if open"""
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

# Global cache instance
_cache_instance: Optional[CacheManager] = None

def get_cache_manager(redis_url: Optional[str] = None) -> CacheManager:
    """
    Get singleton cache manager instance
    
    Args:
        redis_url: Redis connection URL (only used on first call)
        
    Returns:
        CacheManager instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager(redis_url)
    return _cache_instance

# Convenience functions for backward compatibility
async def get_cached(key: str) -> Optional[Any]:
    """Get value from default cache manager"""
    cache = get_cache_manager()
    return await cache.get(key)

async def set_cached(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """Set value in default cache manager"""
    cache = get_cache_manager()
    return await cache.set(key, value, ttl_seconds)

async def delete_cached(key: str) -> bool:
    """Delete key from default cache manager"""
    cache = get_cache_manager()
    return await cache.delete(key)
