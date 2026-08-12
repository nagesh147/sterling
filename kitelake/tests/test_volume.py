"""Relocatable storage: identity-based discovery and graceful absence.

The behaviour under test is the one the user asked for explicitly — unplugging the drive
must produce helpful information, never an error.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from kitelake import volume as V


class TestStamping:
    def test_adopt_creates_layout_and_stamp(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        root = tmp_path / "Lake"
        status = V.adopt_root(root, label="USB")
        assert status.available
        assert (root / V.STAMP_FILENAME).exists()
        for sub in V.SUBDIRS:
            assert (root / sub).is_dir()
        assert status.label == "USB"

    def test_readopt_preserves_identity(self, tmp_path: Path, monkeypatch) -> None:
        """Re-adopting must not mint a new id — that would orphan the stored data."""
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        root = tmp_path / "Lake"
        first = V.adopt_root(root, label="USB")
        second = V.adopt_root(root, label="Renamed")
        assert second.lake_id == first.lake_id
        assert second.label == "Renamed"

    def test_unwritable_target_names_the_fix(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0o500)  # readable, not writable
        try:
            with pytest.raises(V.LakeUnavailable) as err:
                V.adopt_root(locked / "Lake")
            assert "sudo install -d" in str(err.value), "must give the exact remedy"
        finally:
            locked.chmod(0o700)

    def test_registry_lives_outside_the_lake(self, tmp_path: Path, monkeypatch) -> None:
        """It must survive the drive going away."""
        cfg = tmp_path / "cfg"
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(cfg))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        root = tmp_path / "Lake"
        V.adopt_root(root)
        shutil.rmtree(root)
        assert (cfg / "roots.json").exists()
        assert json.loads((cfg / "roots.json").read_text())["known"]


class TestDiscovery:
    def test_rename_self_heals_by_identity(self, tmp_path: Path, monkeypatch) -> None:
        cfg = tmp_path / "cfg"
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(cfg))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        mount = tmp_path / "mount"
        mount.mkdir()
        first = V.adopt_root(mount / "SterlingLake", label="USB")

        os.rename(mount / "SterlingLake", mount / "MarketData")
        status = V.lake_status()
        assert status.available
        assert status.lake_id == first.lake_id
        assert status.root == str(mount / "MarketData")
        # The registry should have been rewritten to the new location.
        entry = json.loads((cfg / "roots.json").read_text())["known"][0]
        assert entry["last_path"] == str(mount / "MarketData")

    def test_env_override_always_wins(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        real = tmp_path / "Real"
        V.adopt_root(real, label="registered")
        other = tmp_path / "Other"
        other.mkdir()
        monkeypatch.setenv("KITELAKE_ROOT", str(other))
        assert V.lake_status().root == str(other)


class TestGracefulAbsence:
    def test_cold_start_explains_itself(self, no_lake) -> None:
        status = V.lake_status()
        assert status.available is False
        assert status.reason
        assert status.guidance, "must tell the user what to do"
        assert any("pick" in g.lower() or "choose" in g.lower() for g in status.guidance)

    def test_missing_drive_reports_last_path_and_options(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        mount = tmp_path / "mount"
        mount.mkdir()
        lake = mount / "SterlingLake"
        V.adopt_root(lake, label="Pendrive")

        # A real unplug takes the whole mount away, not just the lake folder.
        shutil.move(str(lake), str(tmp_path / "moved"))
        shutil.rmtree(mount)

        status = V.lake_status()
        assert status.available is False
        assert "Pendrive" in status.reason
        assert str(lake) == status.last_path
        assert any("plug the drive back in" in g.lower() for g in status.guidance)
        assert any("nothing is lost" in g.lower() for g in status.guidance)

    def test_lake_status_never_raises(self, no_lake) -> None:
        assert V.lake_status().available is False  # the contract: an answer, not an exception

    def test_resolve_root_raises_typed_error_with_guidance(self, no_lake) -> None:
        with pytest.raises(V.LakeUnavailable) as err:
            V.resolve_root()
        assert err.value.guidance, "the exception must carry UI-renderable guidance"

    @pytest.mark.parametrize(
        "accessor",
        ["bars_dir", "instruments_dir", "manifest_dir", "catalog_dir", "logs_dir",
         "staging_dir", "ticks_dir"],
    )
    def test_path_accessors_degrade_typed(self, no_lake, accessor: str) -> None:
        """Never FileNotFoundError — callers key on LakeUnavailable to show guidance."""
        with pytest.raises(V.LakeUnavailable):
            getattr(V, accessor)()


class TestBrowse:
    def test_lists_only_directories(self, tmp_path: Path, no_lake) -> None:
        (tmp_path / "subdir").mkdir()
        (tmp_path / "a_file.txt").write_text("x")
        result = V.browse(tmp_path)
        names = [e["name"] for e in result["entries"]]
        assert "subdir" in names
        assert "a_file.txt" not in names, "picking a folder must not expose files"

    def test_flags_existing_lakes(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        V.adopt_root(tmp_path / "mount" / "Lake", label="Existing")
        result = V.browse(tmp_path / "mount")
        entry = next(e for e in result["entries"] if e["name"] == "Lake")
        assert entry["has_lake"] is True
        assert entry["lake_label"] == "Existing"

    def test_hidden_folders_opt_in(self, tmp_path: Path, no_lake) -> None:
        (tmp_path / ".secret").mkdir()
        assert ".secret" not in [e["name"] for e in V.browse(tmp_path)["entries"]]
        assert ".secret" in [
            e["name"] for e in V.browse(tmp_path, show_hidden=True)["entries"]
        ]

    def test_missing_path_falls_back_without_raising(self, no_lake) -> None:
        result = V.browse("/definitely/not/here")
        assert result["error"]
        assert result["path"] == str(Path.home())

    def test_unreadable_path_reports_cleanly(self, no_lake) -> None:
        result = V.browse("/root")
        assert result["entries"] == []
        # Either a permission message or (if running as root) a clean listing — both fine.
        assert isinstance(result["error"], str)


class TestVolumes:
    def test_enumerates_real_mounts(self, no_lake) -> None:
        volumes = V.list_volumes()
        assert volumes, "at least the root filesystem must be found"
        assert any(v.path == "/" for v in volumes)
        for vol in volumes:
            assert vol.total_bytes >= 0
            assert isinstance(vol.writable, bool)
            assert vol.free_gib == round(vol.free_bytes / 2**30, 2)

    def test_scan_is_fast(self, no_lake) -> None:
        """It runs behind an 8-second UI poll, so it must stay cheap."""
        import time

        start = time.perf_counter()
        V.list_volumes()
        assert time.perf_counter() - start < 2.0
