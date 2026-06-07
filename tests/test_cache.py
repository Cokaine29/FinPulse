"""FinPulse Cache Unit Tests

Tests set, get, delete, clear, and expiry behaviors of the TTLCache class.
"""

import asyncio
import time
import pytest

from finpulse.data.cache import TTLCache


@pytest.mark.asyncio
async def test_cache_set_get():
    cache = TTLCache(default_ttl_seconds=60)
    await cache.set("test_key", "test_value")
    val = await cache.get("test_key")
    assert val == "test_value"


@pytest.mark.asyncio
async def test_cache_expiration():
    # Set a very short TTL (0.1 seconds)
    cache = TTLCache(default_ttl_seconds=0.1)
    await cache.set("expire_key", "value")
    
    # Check immediate retrieval
    val = await cache.get("expire_key")
    assert val == "value"
    
    # Sleep to allow cache item to expire
    await asyncio.sleep(0.15)
    
    # Check retrieval after expiry
    val_expired = await cache.get("expire_key")
    assert val_expired is None


@pytest.mark.asyncio
async def test_cache_delete():
    cache = TTLCache()
    await cache.set("del_key", "value")
    await cache.delete("del_key")
    val = await cache.get("del_key")
    assert val is None


@pytest.mark.asyncio
async def test_cache_clear():
    cache = TTLCache()
    await cache.set("k1", "v1")
    await cache.set("k2", "v2")
    await cache.clear()
    
    assert await cache.get("k1") is None
    assert await cache.get("k2") is None
