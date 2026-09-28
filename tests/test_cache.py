from prebounce import MemoryCache


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_get_set_and_expiry() -> None:
    clock = Clock()
    cache = MemoryCache(clock)
    assert cache.get("k") is None
    cache.set("k", {"a": 1}, 10)
    assert cache.get("k") == {"a": 1}
    clock.now += 9.9
    assert cache.get("k") == {"a": 1}
    clock.now += 0.2
    assert cache.get("k") is None
    assert len(cache) == 0


def test_overwrite_and_non_positive_ttl() -> None:
    cache = MemoryCache(Clock())
    cache.set("k", 1, 10)
    cache.set("k", 2, 10)
    assert cache.get("k") == 2
    cache.set("k", 3, 0)
    assert cache.get("k") is None
