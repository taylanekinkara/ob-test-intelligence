from __future__ import annotations

from pathlib import Path


_LAYER_RULES: list[tuple[str, str]] = [
    ("src/api/Controllers/", "api_controller"),
    ("src/web/Controllers/", "web_controller"),
    ("src/services/Data/Entities/", "entity"),
    ("Providers/", "provider"),
    ("src/services/", "service"),
    ("src/core/", "core_model"),
]


def classify_layer(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    for pattern, layer in _LAYER_RULES:
        if pattern in normalized:
            return layer
    return "unknown"


def classify_layers(file_paths: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for fp in file_paths:
        layer = classify_layer(fp)
        result.setdefault(layer, []).append(fp)
    return result
