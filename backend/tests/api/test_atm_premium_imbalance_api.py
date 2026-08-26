"""API surface for ATM Premium Imbalance.

Also guards the identity the UI depends on: defaults and vocabularies are
published by the backend so the client never keeps a second copy that can drift.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.config import router


def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_get_publishes_identity_defaults_and_vocabularies():
    got = client().get("/api/v1/config/atm-premium-imbalance")
    assert got.status_code == 200
    payload = got.json()

    assert payload["strategy"]["id"] == "atm_premium_imbalance"
    assert payload["strategy"]["name"] == "ATM Premium Imbalance"
    assert payload["strategy"]["contract_version"] == "A230.4"
    # Not live-ready until the A274 gate passes.
    assert payload["strategy"]["live_ready"] is False
    assert payload["strategy"]["enabled"] is True

    d = payload["defaults"]
    assert d["target_points"] == 15.0            # OBSERVED (A231/X1)
    assert d["exit_buffer_points"] == 0.5        # OBSERVED (A231/X3)
    assert d["max_entry_attempts"] == 3          # OBSERVED (A231/E1)
    assert d["max_trades_per_session"] == 1      # OBSERVED (A231/L3)
    assert d["entry_price_policy"] == "MARKETABLE_ASK"
    assert d["quote_mode"] == "COMPATIBILITY"
    assert d["enabled"] is True
    assert d["execution_mode"] == "paper"

    vocab = payload["vocabularies"]
    assert "COMPATIBILITY" in vocab["quote_mode"]
    assert "SYNCHRONIZED" in vocab["quote_mode"]
    assert "EXECUTABLE" in vocab["quote_mode"]
    assert set(vocab["data_source"]) == {"kite", "truedata"}

    # The UI must be told which options validate() will refuse, not discover it
    # through a 422 after the operator has already clicked.
    # The points variant is research-only: no single points buffer fits both
    # decoded sessions. FIRST_TICK_PERCENT is the observed rule.
    assert payload["research_only"]["entry_price_policy"] == ["FIRST_TICK_PLUS_BUFFER"]
    assert "FIRST_TICK_PERCENT" in payload["vocabularies"]["entry_price_policy"]
    assert "PREMIUM_CONVERGENCE" in payload["research_only"]["exit_policy"]


def test_put_round_trip_and_unknown_field_rejected():
    c = client()
    put = c.put("/api/v1/config/atm-premium-imbalance", json={"quantity": 20, "underlying": "SENSEX"})
    assert put.status_code == 200
    assert put.json()["config"]["quantity"] == 20

    bad = c.put("/api/v1/config/atm-premium-imbalance", json={"target_points": -1})
    assert bad.status_code == 422
    assert "target_points" in bad.json()["detail"]


def test_put_rejects_research_only_exit_policy_in_live_mode():
    c = client()
    bad = c.put(
        "/api/v1/config/atm-premium-imbalance",
        json={
            "execution_mode": "live", "quote_mode": "EXECUTABLE", "quantity": 20,
            "protection_mode": "RESTING_TARGET_LIMIT",
            "exit_policy": "PREMIUM_CONVERGENCE",
        },
    )
    assert bad.status_code == 422
    assert "research-only" in bad.json()["detail"]


def test_put_rejects_live_mode_priced_off_cached_ltp():
    c = client()
    bad = c.put(
        "/api/v1/config/atm-premium-imbalance",
        json={"execution_mode": "live", "quote_mode": "COMPATIBILITY", "quantity": 20},
    )
    assert bad.status_code == 422
    assert "EXECUTABLE" in bad.json()["detail"]


def test_snapshot_scopes_to_the_session_and_ignores_a_supplied_user_id():
    """The tenant comes from the auth seam (X-User-Id), never from the request.

    Sterling resolves an absent header to "default" on purpose (single-user local
    use), so the invariant worth guarding is not a 401 -- it is that a caller
    cannot name a *different* tenant and have it honoured.
    """
    c = client()
    plain = c.get("/api/v1/config/atm-premium-imbalance/snapshot")
    assert plain.status_code == 200
    spoofed = c.get(
        "/api/v1/config/atm-premium-imbalance/snapshot?user_id=someone-else"
    )
    assert spoofed.status_code == 200
    # A query-string tenant must have no effect whatsoever.
    assert spoofed.json() == plain.json()


def test_snapshot_reports_blockers_rather_than_pretending_to_be_armed():
    """Derives expectations from the config the snapshot actually reports, so the
    test cannot flake on whatever state an earlier test in the module left."""
    payload = client().get("/api/v1/config/atm-premium-imbalance/snapshot").json()
    cfg, blockers = payload["config"], payload["blockers"]
    assert payload["strategy"]["id"] == "atm_premium_imbalance"
    assert ("strategy disabled" in blockers) == (not cfg["enabled"])
    assert ("quantity not set" in blockers) == (cfg["quantity"] <= 0)
    # No broker account is configured under test, so the pair cannot resolve --
    # and that must be reported, never silently treated as armed.
    assert payload["resolved"] is None
    assert any("instrument resolution failed" in b for b in blockers)


def test_get_publishes_protection_modes_and_live_requirements():
    payload = client().get("/api/v1/config/atm-premium-imbalance").json()
    vocab = payload["vocabularies"]
    assert set(vocab["protection_mode"]) == {"NONE", "RESTING_TARGET_LIMIT", "GTT"}
    assert payload["defaults"]["protection_mode"] == "NONE"   # fidelity by default
    assert payload["defaults"]["expiry_policy"] == "NEAREST"  # corrected 2026-08-21

    # The UI must be able to state live's requirements before the operator tries.
    req = payload["live_requires"]
    assert "NONE" not in req["protection_mode"]
    assert req["quote_mode"] == ["EXECUTABLE"]


def test_put_rejects_live_without_broker_side_protection():
    bad = client().put(
        "/api/v1/config/atm-premium-imbalance",
        json={"execution_mode": "live", "quote_mode": "EXECUTABLE", "quantity": 20,
              "protection_mode": "NONE"},
    )
    assert bad.status_code == 422
    assert "broker-side protection" in bad.json()["detail"]


def test_arm_refuses_while_disabled_rather_than_half_arming():
    c = client()
    c.put("/api/v1/config/atm-premium-imbalance", json={"enabled": False})
    got = c.post("/api/v1/config/atm-premium-imbalance/arm")
    assert got.status_code == 200
    # A refusal with a reason, never a partially armed session.
    assert got.json()["status"] in ("disabled", "no_quantity", "market_closed")


def test_every_config_field_is_settable_through_the_api():
    """The endpoint must not be a filter that drops settings it has not heard of.

    A hand-written request model used to list every field by name and fell behind
    the dataclass, so new settings were silently discarded on the way in: the UI
    looked like it saved and nothing changed. This asserts the two cannot drift.
    """
    from dataclasses import fields
    from app.engines.atm_premium_imbalance import ATMPremiumImbalanceConfig

    c = client()
    served = set(c.get("/api/v1/config/atm-premium-imbalance").json()["config"])
    assert served == {f.name for f in fields(ATMPremiumImbalanceConfig)}

    # and each one actually round-trips, not just appears in the payload
    probes = {
        "sizing_mode": "LOTS", "lots": 2, "stop_basis": "PERCENT",
        "stop_percent": 20.0, "trail_percent": 8.0, "trail_start_percent": 5.0,
        "breakeven_percent": 3.0, "entry_window_seconds": 240,
        "close_at_session_end": False, "target_points": 12.0,
    }
    for key, value in probes.items():
        out = c.put("/api/v1/config/atm-premium-imbalance", json={key: value})
        assert out.status_code == 200, (key, out.text)
        assert out.json()["config"][key] == value, key


def test_an_unknown_setting_is_refused_rather_than_ignored():
    """A dropped setting is worse than a 422: the UI cannot tell it failed."""
    out = client().put("/api/v1/config/atm-premium-imbalance",
                       json={"not_a_real_setting": 1})
    assert out.status_code == 422
    assert "not_a_real_setting" in out.text


def test_an_invalid_value_is_refused_with_its_reason():
    out = client().put("/api/v1/config/atm-premium-imbalance",
                       json={"stop_basis": "SOMETIMES"})
    assert out.status_code == 422
    assert "stop_basis" in out.text


def test_an_empty_body_changes_nothing():
    assert client().put("/api/v1/config/atm-premium-imbalance", json={}).status_code == 422

