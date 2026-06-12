from __future__ import annotations

from app.utils.domain_classifier import classify_domain, classify_domains


def test_bus():
    assert classify_domain("src/services/Bus/BusService.cs") == "bus"


def test_flight():
    assert classify_domain("src/services/Flight/FlightBooking.cs") == "flight"


def test_hotel():
    assert classify_domain("src/services/Hotel/HotelService.cs") == "hotel"


def test_payment():
    assert classify_domain("src/services/Payment/PaymentService.cs") == "payment"


def test_sea():
    assert classify_domain("src/services/Sea/FerryService.cs") == "sea"


def test_unknown():
    assert classify_domain("src/shared/Helper.cs") == "unknown"


def test_classify_domains_dedup():
    domains = classify_domains([
        "src/services/Bus/BusService.cs",
        "src/services/Bus/BusJourney.cs",
    ])
    assert domains == ["bus"]
