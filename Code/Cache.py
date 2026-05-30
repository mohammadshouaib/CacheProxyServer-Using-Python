"""Response cache with two interchangeable backends.

Replaces the old duplicated Cache.py / dictionaryCache.py. Storage only --
the decision of *what* is cacheable lives in the server, so HTTP semantics
are respected in one place. Both backends are thread-safe, expire by TTL,
and evict least-recently-used entries past a configured limit.
"""
import hashlib
import os
import threading
import time
from collections import OrderedDict


def make_key(method, host, port, path):
    """Stable key based on the request identity, not the full header blob,
    so different clients can share cache entries.
    """
    raw = f"{method.upper()} {host}:{port}{path}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class MemoryCache:
    def __init__(self, max_entries):
        self.max = max_entries
        self._lock = threading.Lock()
        self._store = OrderedDict()  # key -> (expires_at, value)

    def get(self, key):
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires, value = item
            if time.time() >= expires:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def put(self, key, value, ttl):
        with self._lock:
            self._store[key] = (time.time() + ttl, value)
            self._store.move_to_end(key)
            while len(self._store) > self.max:
                self._store.popitem(last=False)

    def clear(self):
        with self._lock:
            self._store.clear()


class FileCache:
    def __init__(self, directory, max_entries, max_object_bytes):
        self.dir = directory
        self.max = max_entries
        self.max_object_bytes = max_object_bytes
        self._lock = threading.Lock()
        os.makedirs(directory, exist_ok=True)

    def _path(self, key):
        return os.path.join(self.dir, key)

    def get(self, key):
        path = self._path(key)
        with self._lock:
            try:
                with open(path, "rb") as f:
                    expires = float(f.readline().decode("ascii").strip())
                    value = f.read()
            except (FileNotFoundError, ValueError):
                return None
            if time.time() >= expires:
                self._safe_remove(path)
                return None
            os.utime(path, None)  # touch -> mtime tracks recency for LRU
            return value

    def put(self, key, value, ttl):
        if len(value) > self.max_object_bytes:
            return
        path = self._path(key)
        with self._lock:
            with open(path, "wb") as f:
                f.write(f"{time.time() + ttl}\n".encode("ascii"))
                f.write(value)
            self._evict()

    def _evict(self):
        entries = [os.path.join(self.dir, n) for n in os.listdir(self.dir)]
        if len(entries) <= self.max:
            return
        entries.sort(key=os.path.getmtime)  # oldest (LRU) first
        for path in entries[: len(entries) - self.max]:
            self._safe_remove(path)

    def clear(self):
        with self._lock:
            for name in os.listdir(self.dir):
                self._safe_remove(os.path.join(self.dir, name))

    @staticmethod
    def _safe_remove(path):
        try:
            os.remove(path)
        except OSError:
            pass


def build_cache(cfg):
    c = cfg["cache"]
    if c["backend"] == "memory":
        return MemoryCache(c["max_entries"])
    return FileCache(c["dir"], c["max_entries"], c["max_object_bytes"])