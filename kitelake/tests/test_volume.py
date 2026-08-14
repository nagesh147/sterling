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
    def test_enumerates_real_mounts(self, no_lake, real_mounts) -> None:
        volumes = V.list_volumes()
        assert volumes, "at least the root filesystem must be found"
        assert any(v.path == "/" for v in volumes)
        for vol in volumes:
            assert vol.total_bytes >= 0
            assert isinstance(vol.writable, bool)
            assert vol.free_gib == round(vol.free_bytes / 2**30, 2)

    def test_scan_is_fast(self, no_lake, real_mounts) -> None:
        """It runs behind an 8-second UI poll, so it must stay cheap."""
        import time

        start = time.perf_counter()
        V.list_volumes()
        assert time.perf_counter() - start < 2.0


class TestRegistryConcurrency:
    """Regression tests for a real production failure (2026-08-13).

    ``resolve_root()`` runs on every parquet write, and it refreshes the registry. The
    registry used a single fixed ``roots.json.tmp``, so concurrent download workers raced:
    one won the ``os.replace`` and the others raised FileNotFoundError. Because that ran
    inside the write path, it marked two genuine data chunks (BSL, HINDPETRO) as failed.
    """

    def test_concurrent_resolution_never_raises(self, tmp_path: Path, monkeypatch) -> None:
        import concurrent.futures

        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        V.adopt_root(tmp_path / "Lake", label="USB")

        def hammer(_i: int) -> str:
            # Mirrors what each download worker does before writing a parquet file.
            return str(V.bars_dir())

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(hammer, range(200)))
        assert len({*results}) == 1, "all workers must agree on the bars directory"

    def test_each_write_uses_a_distinct_temp_name(self, tmp_path: Path, monkeypatch) -> None:
        """Locks in the fix for the shipped race, without depending on thread timing.

        The bug was a single fixed ``roots.json.tmp`` shared by every writer: with several
        download workers resolving paths at once, one won the ``os.replace`` and the rest
        raised FileNotFoundError — which is what killed the BSL and HINDPETRO chunks on
        2026-08-13. Asserting the temp path differs per write is deterministic and fails
        against the old implementation, where both writes named the same file.
        """
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        V.adopt_root(tmp_path / "Lake")

        seen: list[str] = []
        real_replace = os.replace

        def spy(src, dst, *a, **kw):
            seen.append(Path(src).name)
            return real_replace(src, dst, *a, **kw)

        monkeypatch.setattr(V.os, "replace", spy)
        for _ in range(5):
            V._write_registry(V.registry())

        assert len(seen) == 5
        assert len(set(seen)) == 5, f"temp names must be unique per write, got {seen}"
        assert "roots.json.tmp" not in seen, "the shared temp name is the bug"

    def test_failed_write_leaves_no_temp_file(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        V.adopt_root(tmp_path / "Lake")
        cfg = tmp_path / "cfg"

        def boom(src, dst, *a, **kw):
            raise OSError(2, "No such file or directory")

        monkeypatch.setattr(V.os, "replace", boom)
        with pytest.raises(OSError):
            V._write_registry(V.registry())
        assert not list(cfg.glob("*.tmp")), "a failed write must clean up after itself"
        # The previous good registry must survive untouched.
        assert json.loads((cfg / "roots.json").read_text())["known"]

    def test_registry_refresh_is_skipped_when_nothing_changed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Without this, a download rewrites the registry thousands of times."""
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        V.adopt_root(tmp_path / "Lake")
        registry_file = tmp_path / "cfg" / "roots.json"
        before = registry_file.stat().st_mtime_ns
        for _ in range(50):
            V.resolve_root()
        assert registry_file.stat().st_mtime_ns == before, "hot path must not rewrite it"

    def test_unwritable_registry_does_not_break_reads(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Bookkeeping must never take down the data path — the actual bug's blast radius."""
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)
        V.adopt_root(tmp_path / "Lake", label="USB")

        def boom(_reg: dict) -> Path:
            raise OSError(2, "No such file or directory")

        monkeypatch.setattr(V, "_write_registry", boom)
        # Force the path to change so _remember actually attempts a write.
        import os as _os

        _os.rename(tmp_path / "Lake", tmp_path / "Renamed")
        assert V.bars_dir().is_dir(), "a failed registry write must not break path resolution"

    def test_adopt_still_surfaces_a_registry_failure(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Advisory on the hot path, but strict when the user explicitly chose a folder."""
        monkeypatch.setenv("KITELAKE_CONFIG_DIR", str(tmp_path / "cfg"))
        monkeypatch.delenv("KITELAKE_ROOT", raising=False)

        def boom(_reg: dict) -> Path:
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(V, "_write_registry", boom)
        with pytest.raises(OSError):
            V.adopt_root(tmp_path / "Lake", label="USB")


class TestShortfallRepair:
    """Detecting and requeueing lost writes.

    A live run silently discarded 21,062,425 candles across 1,394 instruments to a
    read-modify-write race in the writer. The chunks stayed marked ``done``, so resume
    would never have refetched them — the lake would have looked finished while being 12%
    short. These tests pin the detection and the recovery.
    """

    def test_detects_a_shortfall(self, lake: Path) -> None:
        from datetime import date as _date

        from kitelake.manifest import Manifest

        with Manifest() as man:
            man.plan_chunks(1, "minute", [(_date(2026, 2, 13), _date(2026, 4, 13)),
                                          (_date(2026, 4, 14), _date(2026, 6, 12))])
            man.mark_chunk(1, "minute", _date(2026, 2, 13), "done", rows=45_000)
            man.mark_chunk(1, "minute", _date(2026, 4, 14), "done", rows=45_000)
            # Only one chunk's worth survived on disk — the other was clobbered.
            man.upsert_symbol(1, "minute", tradingsymbol="CLOBBERED", rows=45_000, status="ok")

            short = man.shortfall("minute")
            assert len(short) == 1
            assert short[0]["tradingsymbol"] == "CLOBBERED"
            assert short[0]["missing"] == 45_000

    def test_healthy_instrument_is_not_flagged(self, lake: Path) -> None:
        from datetime import date as _date

        from kitelake.manifest import Manifest

        with Manifest() as man:
            man.plan_chunks(2, "minute", [(_date(2026, 2, 13), _date(2026, 4, 13))])
            man.mark_chunk(2, "minute", _date(2026, 2, 13), "done", rows=45_750)
            man.upsert_symbol(2, "minute", tradingsymbol="FINE", rows=45_750, status="ok")
            assert man.shortfall("minute") == []

    def test_min_missing_filters_dedup_noise(self, lake: Path) -> None:
        """candles_to_table drops duplicates, so a tiny gap is expected, not a lost write."""
        from datetime import date as _date

        from kitelake.manifest import Manifest

        with Manifest() as man:
            man.plan_chunks(3, "minute", [(_date(2026, 2, 13), _date(2026, 4, 13))])
            man.mark_chunk(3, "minute", _date(2026, 2, 13), "done", rows=45_752)
            man.upsert_symbol(3, "minute", tradingsymbol="NOISY", rows=45_750, status="ok")
            assert len(man.shortfall("minute", min_missing=1)) == 1
            assert man.shortfall("minute", min_missing=100) == []

    def test_reset_requeues_every_chunk(self, lake: Path) -> None:
        from datetime import date as _date

        from kitelake.manifest import Manifest

        chunks = [(_date(2026, 2, 13), _date(2026, 4, 13)), (_date(2026, 4, 14), _date(2026, 6, 12))]
        with Manifest() as man:
            man.plan_chunks(4, "minute", chunks)
            for a, _b in chunks:
                man.mark_chunk(4, "minute", a, "done", rows=45_000)
            assert man.pending_chunks("minute") == []

            assert man.reset_instruments("minute", [4]) == 2
            pending = man.pending_chunks("minute")
            assert len(pending) == 2, "both chunks must be refetched"
            assert man.stats("minute")["candles"] == 0, "row counts are cleared too"

    def test_reset_with_no_tokens_is_a_noop(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            assert man.reset_instruments("minute", []) == 0


class TestSymbolsPage:
    """SQL-side pagination for the data browser.

    The UI polls this. Loading every stored row and slicing in Python meant reading 7,400+
    rows off the removable drive per request, which was slow enough to degrade the whole
    API under a few concurrent callers.
    """

    def _seed(self, man, n: int = 30) -> None:
        for i in range(n):
            man.upsert_symbol(
                1000 + i, "minute", tradingsymbol=f"SYM{i:03d}", exchange="NSE",
                rows=1000 - i, bytes=100 * (1000 - i), status="ok",
                first_ts="2026-02-13T03:45:00+00:00", last_ts="2026-08-13T09:59:00+00:00",
            )
        # A zero-row symbol is a placeholder, not stored data — it must never be listed.
        man.upsert_symbol(9999, "minute", tradingsymbol="EMPTYONE", rows=0, status="ok")

    def test_paginates_and_reports_total(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            self._seed(man)
            page, total = man.symbols_page("minute", limit=10, offset=0)
            assert total == 30, "total counts every match, not just this page"
            assert len(page) == 10
            second, _ = man.symbols_page("minute", limit=10, offset=10)
            assert {r["instrument_token"] for r in page}.isdisjoint(
                {r["instrument_token"] for r in second}
            ), "pages must not overlap"

    def test_excludes_zero_row_symbols(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            self._seed(man)
            page, total = man.symbols_page("minute", limit=100)
            assert total == 30
            assert all(r["rows"] > 0 for r in page)
            assert "EMPTYONE" not in {r["tradingsymbol"] for r in page}

    def test_default_sort_is_biggest_first(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            self._seed(man)
            page, _ = man.symbols_page("minute", limit=5, sort="rows")
            assert [r["rows"] for r in page] == sorted((r["rows"] for r in page), reverse=True)

    def test_sort_by_symbol_is_ascending(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            self._seed(man)
            page, _ = man.symbols_page("minute", limit=5, sort="tradingsymbol")
            names = [r["tradingsymbol"] for r in page]
            assert names == sorted(names)

    def test_search_matches_symbol_and_token(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            self._seed(man)
            page, total = man.symbols_page("minute", search="SYM01")
            assert total == 10 and all("SYM01" in r["tradingsymbol"] for r in page)
            exact, total_tok = man.symbols_page("minute", search="1005")
            assert total_tok == 1 and exact[0]["instrument_token"] == 1005

    def test_unknown_sort_falls_back_instead_of_injecting(self, lake: Path) -> None:
        """The sort column is interpolated into SQL, so it must be whitelisted."""
        from kitelake.manifest import Manifest

        with Manifest() as man:
            self._seed(man)
            page, _ = man.symbols_page("minute", sort="rows; DROP TABLE symbols", limit=3)
            assert len(page) == 3, "a bogus sort must degrade to the default, not error"
            assert man.symbols_page("minute", limit=1)[1] == 30, "table still intact"

    def test_other_intervals_are_not_mixed_in(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            self._seed(man, n=3)
            man.upsert_symbol(7001, "day", tradingsymbol="DAILY", rows=120, status="ok")
            _, minute_total = man.symbols_page("minute", limit=50)
            _, day_total = man.symbols_page("day", limit=50)
            assert minute_total == 3
            assert day_total == 1
