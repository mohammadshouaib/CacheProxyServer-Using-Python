"""Configuration loading for the proxy server.

All tunables live here (and optionally in a config.json next to this file),
so nothing is hardcoded in the server anymore.
"""
import json
import os

DEFAULTS = {
    "listen_host": "127.0.0.1",
    "listen_port": 8080,
    "max_workers": 50,          # bounded thread pool instead of unbounded threads
    "client_timeout": 10,       # seconds to wait on the client socket
    "upstream_timeout": 15,     # seconds to wait on the origin server
    "max_header_bytes": 64 * 1024,
    "max_body_bytes": 10 * 1024 * 1024,
    # "blacklist" = allow everything except listed hosts
    # "whitelist" = deny everything except listed hosts
    # "off"       = no filtering
    "filter_mode": "blacklist",
    "db_name": "proxy_logs.db",
    "cache": {
        "backend": "file",      # "file" or "memory"
        "dir": "cache_files",
        "default_ttl": 60,      # used only when the origin gives no max-age
        "max_entries": 500,     # LRU eviction past this many objects
        "max_object_bytes": 5 * 1024 * 1024,
    },
}


def load_config(path="config.json"):
    """Return DEFAULTS merged with the user's config.json, if present."""
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        for key, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    return cfg