"""Bounded LRU cache used across the BFS and outer search caches.

Behaves like a dict but evicts the least-recently-used entry when size
exceeds maxsize. Tracks hits/misses for diagnostics.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Hashable


class LRUCache:
    def __init__(self, maxsize: int = 5000):
        self.maxsize = maxsize
        self._data: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: Hashable, default: Any = None) -> Any:
        if key in self._data:
            self._data.move_to_end(key)
            self.hits += 1
            return self._data[key]
        self.misses += 1
        return default

    def __contains__(self, key: Hashable) -> bool:
        return key in self._data

    def __setitem__(self, key: Hashable, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self.maxsize:
            self._data.popitem(last=False)
            self.evictions += 1

    def __getitem__(self, key: Hashable) -> Any:
        self._data.move_to_end(key)
        return self._data[key]

    def __len__(self) -> int:
        return len(self._data)

    def clear(self) -> None:
        """Drop cached entries but preserve lifetime hit/miss/eviction counters.

        The counters reflect total operations on this cache instance over its
        lifetime, not since the last clear — so diagnostics across repeated
        clears (e.g. solver-level bfs() calls within one placement) remain
        meaningful.
        """
        self._data.clear()

    def reset_stats(self) -> None:
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def stats(self) -> str:
        total = self.hits + self.misses
        rate = (100.0 * self.hits / total) if total else 0.0
        return (
            f"size={len(self._data)}/{self.maxsize} "
            f"hits={self.hits} misses={self.misses} "
            f"hit_rate={rate:.1f}% evictions={self.evictions}"
        )
