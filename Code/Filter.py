"""Host filtering.

Fixes the old logic where a host had to satisfy BOTH lists (which blocked
everything by default). Now a single `mode` decides the policy.
"""
import logs


def is_allowed(host, mode):
    mode = (mode or "blacklist").lower()
    if mode == "off":
        return True
    if mode == "whitelist":
        return _in_list(host, "whitelist")
    # default: blacklist mode -> allow unless explicitly blocked
    return not _in_list(host, "blacklist")


def _in_list(host, list_type):
    rows = logs.query(
        "SELECT 1 FROM filters WHERE address = ? AND type = ? LIMIT 1",
        (host, list_type),
    )
    return len(rows) > 0


def add_to_filter_list(address, filter_type):
    logs.execute_with_retry(
        "INSERT OR IGNORE INTO filters (address, type) VALUES (?, ?)",
        (address, filter_type),
    )


def remove_from_filter_list(address, filter_type):
    logs.execute_with_retry(
        "DELETE FROM filters WHERE address = ? AND type = ?",
        (address, filter_type),
    )


def send_forbidden(client_socket):
    body = (b"<html><body><h1>403 Forbidden</h1>"
            b"<p>This host is blocked by the proxy.</p></body></html>")
    response = (
        b"HTTP/1.1 403 Forbidden\r\n"
        b"Content-Type: text/html\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
        b"Connection: close\r\n\r\n" + body
    )
    try:
        client_socket.sendall(response)
    except OSError:
        pass