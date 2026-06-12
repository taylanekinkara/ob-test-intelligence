from __future__ import annotations

from typing import Any


def resolve_field(obj: Any, field_path: str) -> Any:
    current = obj
    tokens = field_path.replace("[", ".").replace("]", ".").split(".")
    for token in tokens:
        if not token:
            continue
        if isinstance(current, dict):
            current = current.get(token)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def check_assertion(response: Any, assertion: dict) -> dict:
    field = assertion["field"]
    operator = assertion["operator"]
    expected = assertion.get("value")

    if hasattr(response, "json"):
        try:
            body = response.json()
        except Exception:
            body = {}
        status_code = response.status_code
    else:
        body = response
        status_code = None

    if field == "status_code":
        actual = status_code
    elif field == "status":
        actual = body.get("status", body.get("Status"))
    else:
        actual = resolve_field(body, field)

    passed = _evaluate(actual, operator, expected)

    return {
        "field": field,
        "expected": expected,
        "actual": actual,
        "passed": passed,
        "reason": "" if passed else f"Expected {operator} {expected!r}, got {actual!r}",
    }


def _evaluate(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "equals":
        return actual == expected
    elif operator == "not_equals":
        return actual != expected
    elif operator == "contains":
        return expected in actual if actual else False
    elif operator == "not_contains":
        return expected not in actual if actual else True
    elif operator == "is_not_empty":
        return bool(actual) and actual != [] and actual != {}
    elif operator == "is_empty":
        return not actual or actual == [] or actual == {}
    elif operator == "is_not_null":
        return actual is not None
    elif operator == "is_null":
        return actual is None
    elif operator == "greater_than":
        return actual > expected if actual is not None else False
    elif operator == "less_than":
        return actual < expected if actual is not None else False
    elif operator == "has_length":
        return len(actual) == expected if actual is not None else False
    return False
