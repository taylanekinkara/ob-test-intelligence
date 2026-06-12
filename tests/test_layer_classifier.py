from __future__ import annotations

from app.utils.layer_classifier import classify_layer, classify_layers


def test_api_controller():
    assert classify_layer("src/api/Controllers/JourneyController.cs") == "api_controller"


def test_web_controller():
    assert classify_layer("src/web/Controllers/HomeController.cs") == "web_controller"


def test_service():
    assert classify_layer("src/services/Bus/BusService.cs") == "service"


def test_entity():
    assert classify_layer("src/services/Data/Entities/BusJourney.cs") == "entity"


def test_core_model():
    assert classify_layer("src/core/Models/SearchRequest.cs") == "core_model"


def test_provider():
    assert classify_layer("src/services/Bus/Providers/VaranProvider.cs") == "provider"


def test_unknown():
    assert classify_layer("README.md") == "unknown"


def test_classify_layers_groups():
    result = classify_layers([
        "src/api/Controllers/A.cs",
        "src/services/B.cs",
        "src/api/Controllers/C.cs",
    ])
    assert len(result["api_controller"]) == 2
    assert len(result["service"]) == 1
