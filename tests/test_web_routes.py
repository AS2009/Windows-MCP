"""Tests for the friendly status page and health endpoint."""

from __future__ import annotations

from windows_mcp.__main__ import _index_html, _register_web_routes


def test_index_html_contains_connection_guide():
    html = _index_html()
    assert "Windows-MCP" in html
    assert "/sse" in html
    assert "Authorization: Bearer" in html
    assert "运行中" in html


def test_register_web_routes_registers_root_and_health():
    class FakeMCP:
        def __init__(self) -> None:
            self.routes: dict[str, tuple] = {}

        def custom_route(self, path, methods=None):
            def deco(handler):
                self.routes[path] = (handler, methods)
                return handler

            return deco

    fake = FakeMCP()
    _register_web_routes(fake)
    assert set(fake.routes) == {"/", "/health"}
    assert fake.routes["/"][1] == ["GET"]
    assert fake.routes["/health"][1] == ["GET"]
    # Handlers are async and callable
    for handler, _ in fake.routes.values():
        assert callable(handler)
