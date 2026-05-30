# Caching Proxy Server (Python)

A multithreaded caching HTTP proxy with request logging, host filtering,
HTTPS (CONNECT) tunnelling, and a Streamlit admin dashboard.

## Run

```bash
pip install -r requirements.txt      # only needed for the dashboard/tests
python server.py                     # starts the proxy (see config.json)
streamlit run interface.py           # optional admin dashboard
pytest                               # run tests
```

Point your client/browser at `127.0.0.1:8080` (configurable in `config.json`).

## Layout

| File           | Responsibility                                           |
|----------------|----------------------------------------------------------|
| `server.py`    | Accept loop, thread pool, request handling, CONNECT      |
| `parse.py`     | HTTP request/response parsing, header rewriting          |
| `cache.py`     | Pluggable cache (memory / file) with TTL + LRU eviction  |
| `filtering.py` | blacklist / whitelist / off filtering                    |
| `logs.py`      | SQLite logging (WAL + retry)                             |
| `interface.py` | Streamlit admin dashboard                                |
| `config.py`    | Defaults + `config.json` loader                          |

## Configuration (`config.json`)

`filter_mode` is `"blacklist"` (allow all but listed), `"whitelist"`
(deny all but listed), or `"off"`. Cache backend, TTL, size limits, timeouts,
and worker count are all configurable.

## Known limitations

- Chunked **request** bodies aren't reassembled (Content-Length only).
- HTTPS is tunnelled, not inspected (no MITM decryption).