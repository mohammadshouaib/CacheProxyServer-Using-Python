"""HTTP parsing helpers.

Headers are treated as latin-1 (the historical HTTP charset) so binary-ish
bytes never raise. Response *bodies* are never decoded here -- they stay as
opaque bytes, which fixes the old UnicodeDecodeError on images/gzip.
"""
from urllib.parse import urlsplit

# Headers that must not be forwarded by a proxy (RFC 7230 sec 6.1).
HOP_BY_HOP = {
    "connection", "proxy-connection", "keep-alive", "proxy-authorization",
    "proxy-authenticate", "te", "trailers", "transfer-encoding", "upgrade",
}


def parse_request_line(head: bytes):
    """Return (method, target, version) from the first line of the request."""
    text = head.decode("iso-8859-1", errors="replace")
    first = text.split("\r\n", 1)[0]
    parts = first.split()
    if len(parts) != 3:
        raise ValueError(f"Malformed request line: {first!r}")
    return parts[0], parts[1], parts[2]


def parse_headers(head: bytes):
    """Parse header lines into an ordered list of (name, value) tuples.

    A list (not a dict) preserves duplicates like multiple Cookie/Set-Cookie
    headers. The leading request/status line is skipped.
    """
    text = head.decode("iso-8859-1", errors="replace")
    headers = []
    for line in text.split("\r\n")[1:]:
        if not line or ":" not in line:
            continue
        name, _, value = line.partition(":")
        headers.append((name.strip(), value.strip()))
    return headers


def get_header(headers, name, default=None):
    """Case-insensitive lookup over a (name, value) list."""
    name = name.lower()
    for k, v in headers:
        if k.lower() == name:
            return v
    return default


def resolve_target(method, target, headers, default_port=80):
    """Work out (host, port, origin_form_path) for any proxy request form.

    Handles absolute-form (`GET http://host/p`), origin-form (`GET /p` + Host
    header) and CONNECT (`CONNECT host:port`). Raises if no host can be found.
    """
    if method.upper() == "CONNECT":
        host, _, port = target.partition(":")
        if not host:
            raise ValueError("CONNECT target missing host")
        return host, int(port or 443), None

    if target.startswith(("http://", "https://")):
        u = urlsplit(target)
        host = u.hostname
        port = u.port or (443 if u.scheme == "https" else 80)
        path = u.path or "/"
        if u.query:
            path += "?" + u.query
    else:
        host_header = get_header(headers, "host", "")
        host, _, port_str = host_header.partition(":")
        port = int(port_str) if port_str else default_port
        path = target or "/"

    if not host:
        raise ValueError("Could not determine target host")
    return host, port, path


def _host_header_value(host, port):
    return host if port in (80, 443) else f"{host}:{port}"


def build_forward_request(method, path, version, headers, body, host, port):
    """Rebuild an origin-form request: strip hop-by-hop headers, normalise
    Host, and force `Connection: close` so the upstream read loop terminates.
    """
    kept = [(k, v) for (k, v) in headers
            if k.lower() not in HOP_BY_HOP and k.lower() != "host"]
    lines = [f"{method} {path} {version}",
             f"Host: {_host_header_value(host, port)}"]
    lines += [f"{k}: {v}" for k, v in kept]
    lines.append("Connection: close")
    head = ("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1")
    return head + body


def parse_response_status(head: bytes):
    """Pull the numeric status code out of a response header block, or None."""
    try:
        first = head.split(b"\r\n", 1)[0].decode("iso-8859-1")
        return int(first.split()[1])
    except (ValueError, IndexError):
        return None