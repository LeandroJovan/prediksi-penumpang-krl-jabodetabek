import pytest

from backend.app.core.cache import InMemoryCache


async def test_cache_is_bounded_and_evicts_oldest():
    cache = InMemoryCache(max_entries=3)
    for i in range(5):
        await cache.set(f"k{i}", str(i))
    assert len(cache._store) == 3
    assert await cache.get("k0") is None
    assert await cache.get("k4") == "4"


async def test_cache_get_refreshes_recency():
    cache = InMemoryCache(max_entries=2)
    await cache.set("a", "1")
    await cache.set("b", "2")
    assert await cache.get("a") == "1"  # a menjadi paling baru
    await cache.set("c", "3")  # b yang terbuang
    assert await cache.get("b") is None
    assert await cache.get("a") == "1"


async def test_cache_expired_entries_are_purged_before_eviction(monkeypatch):
    import backend.app.core.cache as mod

    now = [1000.0]
    monkeypatch.setattr(mod.time, "time", lambda: now[0])
    cache = InMemoryCache(max_entries=2)
    await cache.set("old", "x", ex=10)
    await cache.set("keep", "y")
    now[0] += 60
    await cache.set("new", "z")
    assert await cache.get("keep") == "y"
    assert await cache.get("new") == "z"
    assert await cache.get("old") is None


def test_cache_rejects_invalid_size():
    with pytest.raises(ValueError):
        InMemoryCache(max_entries=0)
