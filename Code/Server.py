"""Caching HTTP proxy server.

Key fixes over the original:
  * Reads the full request by framing on the header terminator and
    Content-Length, instead of a non-blocking loop that truncated randomly.
  * Streams response bytes through untouched (no UTF-8 decode of binaries).
  * Bounded ThreadPoolExecutor instead of unbounded threads.
  * Socket timeouts everywhere so a stalled peer can't pin a worker forever.
  * Cacheability decided by HTTP method/status/Cache-Control, not blindly.
  * Real HTTPS support via CONNECT tunnelling.
"""
import logging
import select
import socket
import time
from concurrent.futures import ThreadPoolExecutor

import cache as cachelib
import config
import filtering
import logs
import parse

BUFSIZE = 65536
CACHEABLE_STATUS = {200, 203, 300, 301, 308}


def recv_full_request(sock, max_header, max_body):
    """Read headers until the blank-line terminator, then any Content-Length
    body. Returns (head_bytes, headers_list, body_bytes).
    """
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(BUFSIZE)
        if not chunk:
            break
        buf += chunk
        if len(buf) > max_header:
            raise ValueError("Request header too large")

    head, _, body = buf.partition(b"\r\n\r\n")
    if not head:
        return b"", [], b""

    headers = parse.parse_headers(head)
    content_length = parse.get_header(headers, "content-length")
    if content_length:
        try:
            needed = int(content_length)
        except ValueError:
            needed = 0
        if needed > max_body:
            raise ValueError("Request body too large")
        while len(body) < needed:
            chunk = sock.recv(BUFSIZE)
            if not chunk:
                break
            body += chunk
    return head, headers, body


def tunnel(client_sock, host, port, timeout):
    """Blindly relay bytes both ways for a CONNECT (HTTPS) tunnel."""
    upstream = socket.create_connection((host, port), timeout=timeout)
    client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    client_sock.setblocking(False)
    upstream.setblocking(False)
    peers = [client_sock, upstream]
    try:
        while True:
            readable, _, errored = select.select(peers, [], peers, timeout)
            if errored or not readable:
                break
            for sock in readable:
                other = upstream if sock is client_sock else client_sock
                try:
                    data = sock.recv(BUFSIZE)
                except (BlockingIOError, InterruptedError):
                    continue
                if not data:
                    return
                other.sendall(data)
    finally:
        try:
            upstream.close()
        except OSError:
            pass


def _compute_ttl(resp_headers, status, default_ttl):
    """Return a TTL in seconds, or None if the response must not be cached."""
    if status not in CACHEABLE_STATUS:
        return None
    cc = (parse.get_header(resp_headers, "cache-control", "") or "").lower()
    if any(d in cc for d in ("no-store", "no-cache", "private")):
        return None
    for part in cc.split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                return max(0, int(part.split("=", 1)[1]))
            except ValueError:
                pass
    return default_ttl


def serve_http(client_sock, host, port, method, path, forward,
               request_id, cfg, cache):
    """Handle a plain HTTP request: try cache, else fetch + stream + maybe store."""
    cacheable_request = method.upper() == "GET"
    key = cachelib.make_key(method, host, port, path)

    if cacheable_request:
        cached = cache.get(key)
        if cached is not None:
            client_sock.sendall(cached)
            head = cached.split(b"\r\n\r\n", 1)[0]
            status = parse.parse_response_status(head)
            ctype = parse.get_header(parse.parse_headers(head),
                                     "content-type", "unknown")
            logs.log_response(request_id, "HIT", status, ctype, len(cached), 0)
            logs.update_request_status(request_id, status or 0)
            return

    start = time.time()
    head_buf = b""
    head_done = False
    total = 0
    cache_buf = bytearray()
    capturing = cacheable_request
    cache_limit = cfg["cache"]["max_object_bytes"]

    upstream = socket.create_connection((host, port), timeout=cfg["upstream_timeout"])
    upstream.settimeout(cfg["upstream_timeout"])
    try:
        upstream.sendall(forward)
        while True:
            chunk = upstream.recv(BUFSIZE)
            if not chunk:
                break
            client_sock.sendall(chunk)        # stream straight through
            total += len(chunk)
            if not head_done:
                head_buf += chunk
                if b"\r\n\r\n" in head_buf:
                    head_done = True
            if capturing:
                cache_buf += chunk
                if len(cache_buf) > cache_limit:   # too big to cache; keep relaying
                    capturing = False
                    cache_buf = bytearray()
    finally:
        try:
            upstream.close()
        except OSError:
            pass

    elapsed_ms = (time.time() - start) * 1000
    head = head_buf.split(b"\r\n\r\n", 1)[0]
    status = parse.parse_response_status(head)
    resp_headers = parse.parse_headers(head)

    if capturing and head_done:
        ttl = _compute_ttl(resp_headers, status, cfg["cache"]["default_ttl"])
        if ttl:
            cache.put(key, bytes(cache_buf), ttl)

    logs.log_response(request_id, "MISS", status,
                      parse.get_header(resp_headers, "content-type", "unknown"),
                      total, elapsed_ms)
    logs.update_request_status(request_id, status or 0)


def handle_client(client_sock, addr, cfg, cache):
    client_ip, client_port = addr
    request_id = None
    try:
        client_sock.settimeout(cfg["client_timeout"])
        head, headers, body = recv_full_request(
            client_sock, cfg["max_header_bytes"], cfg["max_body_bytes"])
        if not head:
            return

        method, target, version = parse.parse_request_line(head)
        host, port, path = parse.resolve_target(method, target, headers)
        logging.info("%s:%s -> %s %s:%s", client_ip, client_port, method, host, port)

        request_id = logs.log_request(
            client_ip, client_port, host, port, method, target, version)

        if not filtering.is_allowed(host, cfg["filter_mode"]):
            filtering.send_forbidden(client_sock)
            logs.log_response(request_id, "MISS", 403, "text/html", 0, 0)
            logs.update_request_status(request_id, 403)
            return

        if method.upper() == "CONNECT":
            tunnel(client_sock, host, port, cfg["upstream_timeout"])
            logs.update_request_status(request_id, 200)
            return

        forward = parse.build_forward_request(
            method, path, version, headers, body, host, port)
        serve_http(client_sock, host, port, method, path, forward,
                   request_id, cfg, cache)

    except Exception as e:  # noqa: BLE001 - log and keep the server alive
        logging.warning("Error handling %s:%s -> %s", client_ip, client_port, e)
        if request_id is None:
            logs.log_request(client_ip, client_port, "unknown", 0,
                             "unknown", "unknown", "unknown", error_message=str(e))
    finally:
        try:
            client_sock.close()
        except OSError:
            pass


def main():
    cfg = config.load_config()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    logs.configure(cfg["db_name"])
    logs.init_db()
    cache = cachelib.build_cache(cfg)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((cfg["listen_host"], cfg["listen_port"]))
    server.listen(128)
    logging.info("Proxy listening on %s:%s  (filter=%s, cache=%s)",
                 cfg["listen_host"], cfg["listen_port"],
                 cfg["filter_mode"], cfg["cache"]["backend"])

    with ThreadPoolExecutor(max_workers=cfg["max_workers"]) as pool:
        try:
            while True:
                client_sock, addr = server.accept()
                pool.submit(handle_client, client_sock, addr, cfg, cache)
        except KeyboardInterrupt:
            logging.info("Shutting down.")
        finally:
            server.close()


if __name__ == "__main__":
    main()