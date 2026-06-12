from __future__ import annotations

from app.utils.assertion_engine import check_assertion, resolve_field


class MockResponse:
    def __init__(self, body: dict, status_code: int = 200):
        self._body = body
        self.status_code = status_code

    def json(self):
        return self._body


def test_equals():
    resp = MockResponse({"status": "Success"})
    result = check_assertion(resp, {"field": "status", "operator": "equals", "value": "Success"})
    assert result["passed"] is True


def test_equals_fail():
    resp = MockResponse({"status": "Error"})
    result = check_assertion(resp, {"field": "status", "operator": "equals", "value": "Success"})
    assert result["passed"] is False


def test_is_not_empty():
    resp = MockResponse({"data": [1, 2, 3]})
    result = check_assertion(resp, {"field": "data", "operator": "is_not_empty"})
    assert result["passed"] is True


def test_is_not_null():
    resp = MockResponse({"key": "value"})
    result = check_assertion(resp, {"field": "key", "operator": "is_not_null"})
    assert result["passed"] is True


def test_is_null():
    resp = MockResponse({"key": None})
    result = check_assertion(resp, {"field": "key", "operator": "is_null"})
    assert result["passed"] is True


def test_nested_field():
    resp = MockResponse({"data": {"journeys": [{"id": 1}]}})
    result = check_assertion(resp, {"field": "data.journeys", "operator": "is_not_empty"})
    assert result["passed"] is True


def test_status_code():
    resp = MockResponse({}, status_code=200)
    result = check_assertion(resp, {"field": "status_code", "operator": "equals", "value": 200})
    assert result["passed"] is True


def test_resolve_field_deep():
    obj = {"a": {"b": {"c": 42}}}
    assert resolve_field(obj, "a.b.c") == 42


def test_resolve_field_array():
    obj = {"items": [10, 20, 30]}
    assert resolve_field(obj, "items[1]") == 20
