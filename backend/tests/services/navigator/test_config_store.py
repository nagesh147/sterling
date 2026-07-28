"""Phase 1 tests: Navigator config persistence — revisioning, activation
watermark semantics, and fail-closed error surfacing (spec §3.2.C, §6.9,
§17.3, §20.7)."""
from __future__ import annotations

import os
import tempfile

import pytest

from app.engines.navigator.schemas import NavigatorConfigModel
from app.services import db
from app.services.navigator import config_store, repository
from app.services.navigator.repository import NavigatorStorageError, RevisionConflict

_UNDERLYINGS = ["NIFTY 50", "NIFTY BANK"]


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    yield
    os.unlink(path)


def _get(user_id="user-1"):
    return config_store.get(user_id, default_underlyings=_UNDERLYINGS)


class TestDefaultCreation:
    def test_first_get_creates_disabled_default_at_revision_1(self):
        rec = _get()
        assert rec.revision == 1
        assert rec.config.enabled is False
        assert rec.config.operating_mode == "advisory"
        assert rec.calibration_readiness == "not_ready"
        assert rec.activation_watermark_ms == 0

    def test_default_underlyings_mirror_caller_supplied_list(self):
        rec = _get()
        assert rec.config.underlyings == _UNDERLYINGS

    def test_get_is_idempotent(self):
        rec1 = _get()
        rec2 = _get()
        assert rec1.revision == rec2.revision == 1

    def test_users_are_isolated(self):
        rec_a = _get("user-a")
        cfg_b = NavigatorConfigModel.default_for(["SENSEX"])
        rec_b = config_store.save(
            "user-b", cfg_b, expected_revision=1, default_underlyings=["SENSEX"]
        )
        assert rec_a.config.underlyings == _UNDERLYINGS
        assert rec_b.config.underlyings == ["SENSEX"]
        assert _get("user-a").config.underlyings == _UNDERLYINGS


class TestSaveAndRevision:
    def test_save_increments_revision(self):
        rec = _get()
        new_cfg = rec.config.model_copy(update={"flow_sample_seconds": 90})
        saved = config_store.save(
            "user-1", new_cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS
        )
        assert saved.revision == 2
        assert saved.config.flow_sample_seconds == 90

    def test_stale_expected_revision_raises_conflict(self):
        rec = _get()
        new_cfg = rec.config.model_copy(update={"flow_sample_seconds": 90})
        config_store.save(
            "user-1", new_cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS
        )
        with pytest.raises(RevisionConflict) as excinfo:
            config_store.save(
                "user-1", new_cfg, expected_revision=rec.revision,  # stale now
                default_underlyings=_UNDERLYINGS,
            )
        assert excinfo.value.current is not None
        assert excinfo.value.current["revision"] == 2

    def test_conflict_leaves_prior_config_active(self):
        rec = _get()
        good_cfg = rec.config.model_copy(update={"flow_sample_seconds": 90})
        config_store.save(
            "user-1", good_cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS
        )
        bad_cfg = rec.config.model_copy(update={"flow_sample_seconds": 45})
        with pytest.raises(RevisionConflict):
            config_store.save(
                "user-1", bad_cfg, expected_revision=rec.revision,
                default_underlyings=_UNDERLYINGS,
            )
        # prior successful write (90) remains active — the rejected stale
        # write (45) never applied.
        assert _get().config.flow_sample_seconds == 90

    def test_wrong_schema_version_rejected(self):
        rec = _get()
        bad_cfg = rec.config.model_copy(update={"schema_version": 2})
        with pytest.raises(ValueError):
            config_store.save(
                "user-1", bad_cfg, expected_revision=rec.revision,
                default_underlyings=_UNDERLYINGS,
            )


class TestActivationWatermark:
    def test_enabling_stamps_a_fresh_watermark(self):
        rec = _get()
        assert rec.activation_watermark_ms == 0
        enabled_cfg = rec.config.model_copy(update={"enabled": True})
        saved = config_store.save(
            "user-1", enabled_cfg, expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS,
        )
        assert saved.config.enabled is True
        assert saved.activation_watermark_ms > 0

    def test_staying_enabled_does_not_move_watermark(self):
        rec = _get()
        enabled_cfg = rec.config.model_copy(update={"enabled": True})
        saved1 = config_store.save(
            "user-1", enabled_cfg, expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS,
        )
        still_enabled = saved1.config.model_copy(update={"flow_sample_seconds": 100})
        saved2 = config_store.save(
            "user-1", still_enabled, expected_revision=saved1.revision,
            default_underlyings=_UNDERLYINGS,
        )
        assert saved2.activation_watermark_ms == saved1.activation_watermark_ms

    def test_disable_then_reenable_gets_a_new_watermark(self):
        rec = _get()
        enabled_cfg = rec.config.model_copy(update={"enabled": True})
        saved1 = config_store.save(
            "user-1", enabled_cfg, expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS,
        )
        disabled_cfg = saved1.config.model_copy(update={"enabled": False})
        saved2 = config_store.save(
            "user-1", disabled_cfg, expected_revision=saved1.revision,
            default_underlyings=_UNDERLYINGS,
        )
        assert saved2.activation_watermark_ms == saved1.activation_watermark_ms  # unchanged on disable

        reenabled_cfg = saved2.config.model_copy(update={"enabled": True})
        saved3 = config_store.save(
            "user-1", reenabled_cfg, expected_revision=saved2.revision,
            default_underlyings=_UNDERLYINGS,
        )
        assert saved3.activation_watermark_ms >= saved1.activation_watermark_ms

    def test_client_cannot_supply_a_watermark_field(self):
        # NavigatorConfigModel structurally has no activation_watermark_ms
        # field at all — the server derives it purely from the enabled
        # transition, so there's nothing for a client payload to smuggle.
        assert "activation_watermark_ms" not in NavigatorConfigModel.model_fields


class TestReset:
    def test_reset_restores_disabled_defaults(self):
        rec = _get()
        enabled_cfg = rec.config.model_copy(update={"enabled": True, "flow_sample_seconds": 200})
        config_store.save(
            "user-1", enabled_cfg, expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS,
        )
        reset_rec = config_store.reset("user-1", default_underlyings=_UNDERLYINGS)
        assert reset_rec.config.enabled is False
        assert reset_rec.config.flow_sample_seconds == 60
        assert reset_rec.revision == 3  # default(1) -> enabled(2) -> reset(3)

    def test_reset_never_re_enables(self):
        reset_rec = config_store.reset("user-1", default_underlyings=_UNDERLYINGS)
        assert reset_rec.config.enabled is False


class TestValidateIsDryRun:
    def test_validate_rejects_bad_payload_without_persisting(self):
        rec = _get("user-dry-run")
        bad_payload = rec.config.model_dump(mode="json")
        bad_payload["fusion"]["base_weight"] = 999  # breaks the weights-sum-to-100 rule
        with pytest.raises(Exception):
            config_store.validate(bad_payload)
        # no phantom revision bump from a failed validate-only call
        assert _get("user-dry-run").revision == 1

    def test_validate_accepts_good_payload(self):
        rec = _get("user-dry-run-2")
        payload = rec.config.model_dump(mode="json")
        validated = config_store.validate(payload)
        assert isinstance(validated, NavigatorConfigModel)


class TestAuditTrail:
    def test_each_save_appends_an_audit_row(self):
        rec = _get("user-audit")
        cfg2 = rec.config.model_copy(update={"flow_sample_seconds": 75})
        config_store.save(
            "user-audit", cfg2, expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS,
        )
        history = config_store.audit_history("user-audit")
        assert len(history) == 1
        assert history[0]["revision"] == 2
        assert history[0]["new_hash"]


class TestStorageUnavailableFailsClosed:
    def test_save_raises_when_store_unavailable(self, monkeypatch):
        rec = _get("user-fragile")
        monkeypatch.setattr(db, "_available", False)
        new_cfg = rec.config.model_copy(update={"flow_sample_seconds": 99})
        with pytest.raises(NavigatorStorageError):
            config_store.save(
                "user-fragile", new_cfg, expected_revision=rec.revision,
                default_underlyings=_UNDERLYINGS,
            )

    def test_save_failure_never_returns_a_fake_success(self, monkeypatch):
        """There is no code path here that could return HTTP 200 with a
        silently discarded write — repository raises, config_store
        propagates, nothing catches it."""
        rec = _get("user-fragile-2")
        monkeypatch.setattr(repository, "compare_and_swap_config", lambda *a, **k: (_ for _ in ()).throw(
            NavigatorStorageError("disk full")
        ))
        new_cfg = rec.config.model_copy(update={"flow_sample_seconds": 99})
        with pytest.raises(NavigatorStorageError):
            config_store.save(
                "user-fragile-2", new_cfg, expected_revision=rec.revision,
                default_underlyings=_UNDERLYINGS,
            )
