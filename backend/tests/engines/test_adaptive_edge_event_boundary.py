from app.engines.adaptive_edge.event_boundary import CanonicalEventBoundary


def test_canonical_event_boundary_preserves_identity_and_timestamps():
    event = CanonicalEventBoundary.create(
        record_id="evt-1",
        event_type="MARKET_TICK",
        instrument_id="NIFTY",
        event_time="2026-08-14T03:45:00+00:00",
        available_at="2026-08-14T03:45:01+00:00",
        source="fixture",
        source_version="fixture-v1",
        payload={"price": 25000.0},
        source_timestamp="2026-08-14T03:45:00+00:00",
        receipt_timestamp="2026-08-14T03:45:01+00:00",
        sequence=7,
    )

    assert event.record_id == "evt-1"
    assert event.instrument_id == "NIFTY"
    assert event.event_time == "2026-08-14T03:45:00+00:00"
    assert event.available_at == "2026-08-14T03:45:01+00:00"
    assert event.sequence == 7


def test_canonical_event_payload_is_immutable():
    event = CanonicalEventBoundary.create(
        record_id="evt-1",
        event_type="MARKET_TICK",
        instrument_id="NIFTY",
        event_time="2026-08-14T03:45:00+00:00",
        available_at="2026-08-14T03:45:00+00:00",
        source="fixture",
        source_version="fixture-v1",
        payload={"price": 25000.0},
    )

    try:
        event.payload["price"] = 1.0
    except TypeError:
        pass
    else:
        raise AssertionError("canonical payload must be immutable")


def test_availability_cannot_precede_event_time():
    try:
        CanonicalEventBoundary.create(
            record_id="evt-1",
            event_type="MARKET_TICK",
            instrument_id="NIFTY",
            event_time="2026-08-14T03:45:00+00:00",
            available_at="2026-08-14T03:44:59+00:00",
            source="fixture",
            source_version="fixture-v1",
            payload={},
        )
    except ValueError as exc:
        assert "available_at cannot precede event_time" in str(exc)
    else:
        raise AssertionError("invalid availability timestamp must be rejected")
