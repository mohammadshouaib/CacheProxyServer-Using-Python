"""Tiny smoke-test client: send one request through the proxy.

Usage:  python client.py            (uses proxy at 127.0.0.1:8080)
Sends an absolute-form request, as a real proxy client would.
"""
import socket

PROXY_HOST, PROXY_PORT = "127.0.0.1", 8080

request = (
    "GET http://example.com/ HTTP/1.1\r\n"
    "Host: example.com\r\n"
    "Connection: close\r\n"
    "\r\n"
).encode("ascii")

with socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=15) as sock:
    sock.sendall(request)
    response = b""
    while True:
        data = sock.recv(65536)
        if not data:
            break
        response += data

# Decode only the header block; leave the body as bytes (could be binary).
head, _, body = response.partition(b"\r\n\r\n")
print(head.decode("iso-8859-1", errors="replace"))
print(f"\n[body: {len(body)} bytes]")