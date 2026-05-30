"""Unit tests for parse.py -- run with: pytest"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import parse  # noqa: E402


def test_request_line():
    assert parse.parse_request_line(b"GET /path HTTP/1.1\r\n") == (
        "GET", "/path", "HTTP/1.1")


def test_request_line_malformed():
    import pytest
    with pytest.raises(ValueError):
        parse.parse_request_line(b"GARBAGE\r\n")


def test_resolve_origin_form():
    headers = [("Host", "example.com")]
    assert parse.resolve_target("GET", "/p", headers) == ("example.com", 80, "/p")


def test_resolve_absolute_form():
    host, port, path = parse.resolve_target(
        "GET", "http://example.com:8080/a?b=1", [])
    assert (host, port, path) == ("example.com", 8080, "/a?b=1")


def test_resolve_connect():
    assert parse.resolve_target("CONNECT", "example.com:443", []) == (
        "example.com", 443, None)


def test_resolve_missing_host_raises():
    import pytest
    with pytest.raises(ValueError):
        parse.resolve_target("GET", "/p", [])


def test_build_forward_strips_hop_by_hop_and_forces_close():
    headers = [("Host", "old"), ("Proxy-Authorization", "secret"),
               ("Connection", "keep-alive"), ("Accept", "*/*")]
    out = parse.build_forward_request(
        "GET", "/p", "HTTP/1.1", headers, b"", "example.com", 80)
    text = out.decode("iso-8859-1")
    assert "Proxy-Authorization" not in text
    assert "keep-alive" not in text
    assert "Connection: close" in text
    assert "Host: example.com" in text
    assert "Accept: */*" in text


def test_parse_response_status():
    assert parse.parse_response_status(b"HTTP/1.1 404 Not Found\r\n") == 404
    assert parse.parse_response_status(b"garbage") is None