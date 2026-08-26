"""Relocatable lake roots: find the data wherever it is, and degrade gracefully.

The data lake lives on whatever volume the user chose — typically a removable drive.
That means two things must be true at all times:

1. **The path is not the identity.** A USB drive mounts at
   ``/run/media/<user>/<fs-uuid>`` today and somewhere else tomorrow. So each lake is
   stamped with a ``LAKE_ID.json`` file containing a stable UUID, and we find the lake
   by looking for that stamp across mounted volumes. If the drive reappears at a new
   path, the registry self-heals.

2. **"Not plugged in" is a normal state, not an error.** Nothing in this module raises
   a bare traceback at the caller. :func:`lake_status` always returns a structured
   answer, and :class:`LakeUnavailable` carries everything a UI needs to help the user:
   what it was looking for, where it last saw it, whether the volume is physically
   present but unmounted, and which other volumes are viable right now.

The registry itself lives in ``~/.config/kitelake/roots.json`` — deliberately NOT on the
lake, so unplugging the drive never loses the bookkeeping that tells us where to look.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import DEFAULT_LAKE_DIRNAME, ROOTS_FILE, config_dir

__all__ = [
    "STAMP_FILENAME",
    "SUBDIRS",
    "LakeUnavailable",
    "LakeStamp",
    "VolumeInfo",
    "LakeStatus",
    "resolve_root",
    "lake_status",
    "list_volumes",
    "browse",
    "adopt_root",
    "forget_root",
    "set_active",
    "registry",
    "bars_dir",
    "instruments_dir",
    "manifest_dir",
    "catalog_dir",
    "logs_dir",
    "staging_dir",
    "ticks_dir",
    "ensure_layout",
]

STAMP_FILENAME = "LAKE_ID.json"
SCHEMA_VERSION = 1

#: Directories that make up a lake. Created on adopt, and idempotently on demand.
SUBDIRS = ("bars", "instruments", "manifest", "catalog", "logs", "_staging", "ticks")

#: Filesystems that can plausibly hold a data lake. Everything else (proc, sysfs,
#: cgroup, tmpfs, squashfs snap mounts…) is skipped when scanning for volumes.
_REAL_FSTYPES = frozenset(
    {
        "ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "jfs", "reiserfs", "zfs",
        "vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "hfsplus", "apfs", "ufs",
    }
)

#: Mount points that are never sensible lake locations even if the fstype passes.
_SKIP_MOUNT_PREFIXES = ("/boot", "/snap", "/var/snap", "/proc", "/sys", "/run/lock")


# ─── Errors ──────────────────────────────────────────────────────────────────
class LakeUnavailable(RuntimeError):
    """The configured lake cannot be reached right now.

    This is an *expected* condition (drive unplugged, remounted elsewhere, never set
    up). Callers that face a user should catch it and render :attr:`guidance` rather
    than surfacing a traceback.
    """

    def __init__(self, message: str, *, guidance: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.guidance: dict[str, Any] = guidance or {}


# ─── Value types ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class LakeStamp:
    """Contents of ``LAKE_ID.json`` — the stable identity of a lake."""

    lake_id: str
    label: str
    created_at: str
    schema_version: int = SCHEMA_VERSION

    @staticmethod
    def new(label: str) -> "LakeStamp":
        return LakeStamp(
            lake_id=str(uuid.uuid4()),
            label=label,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    @staticmethod
    def read(root: Path) -> "LakeStamp | None":
        """Read the stamp at ``root``, or None if absent/unreadable/malformed."""
        try:
            blob = json.loads((root / STAMP_FILENAME).read_text())
            return LakeStamp(
                lake_id=str(blob["lake_id"]),
                label=str(blob.get("label") or root.name),
                created_at=str(blob.get("created_at") or ""),
                schema_version=int(blob.get("schema_version") or 1),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def write(self, root: Path) -> Path:
        path = root / STAMP_FILENAME
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")
        return path


@dataclass
class VolumeInfo:
    """A mounted filesystem the user could put a lake on (or already has)."""

    path: str
    fstype: str
    device: str
    total_bytes: int
    free_bytes: int
    writable: bool
    removable: bool
    volume_uuid: str = ""
    label: str = ""
    #: Set when a stamped lake was found at this path or one level below it.
    lake_at: str = ""
    lake_id: str = ""
    lake_label: str = ""

    @property
    def free_gib(self) -> float:
        return round(self.free_bytes / 2**30, 2)

    @property
    def total_gib(self) -> float:
        return round(self.total_bytes / 2**30, 2)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["free_gib"] = self.free_gib
        d["total_gib"] = self.total_gib
        return d


@dataclass
class LakeStatus:
    """A complete, never-throwing answer to "can I read the lake right now?"."""

    available: bool
    root: str = ""
    lake_id: str = ""
    label: str = ""
    reason: str = ""
    #: Human-readable, actionable sentences for a UI to display verbatim.
    guidance: list[str] = field(default_factory=list)
    last_path: str = ""
    volume_uuid: str = ""
    #: True when the drive is attached but not mounted — a very different fix than
    #: "the drive is missing" (mount it vs plug it in).
    volume_present_unmounted: bool = False
    free_bytes: int = 0
    total_bytes: int = 0
    candidates: list[dict[str, Any]] = field(default_factory=list)
    known: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["free_gib"] = round(self.free_bytes / 2**30, 2) if self.free_bytes else 0.0
        d["total_gib"] = round(self.total_bytes / 2**30, 2) if self.total_bytes else 0.0
        return d


# ─── Registry ────────────────────────────────────────────────────────────────
def _empty_registry() -> dict[str, Any]:
    return {"version": 1, "active_lake_id": "", "known": []}


def registry() -> dict[str, Any]:
    """Read the roots registry. Returns an empty registry rather than raising."""
    path = config_dir() / "roots.json"
    try:
        blob = json.loads(path.read_text())
    except (OSError, ValueError):
        return _empty_registry()
    if not isinstance(blob, dict) or not isinstance(blob.get("known"), list):
        return _empty_registry()
    blob.setdefault("version", 1)
    blob.setdefault("active_lake_id", "")
    return blob


def _write_registry(reg: dict[str, Any]) -> Path:
    """Atomically replace the registry.

    The temp name carries the pid **and** a random suffix. A single fixed
    ``roots.json.tmp`` looks atomic but is not concurrency-safe: with several download
    workers resolving paths at once, they all write the same temp file and only the first
    ``os.replace`` finds it — the rest raise FileNotFoundError. That actually happened,
    and because ``resolve_root()`` sits on the parquet write path it took two real data
    chunks down with it (BSL and HINDPETRO, 2026-08-13).
    """
    path = config_dir() / "roots.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"roots.json.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(json.dumps(reg, indent=2) + "\n")
        os.replace(tmp, path)  # atomic: a crash never leaves a truncated registry
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return path


def _remember(
    stamp: LakeStamp,
    root: Path,
    *,
    volume_uuid: str = "",
    make_active: bool = False,
    required: bool = False,
) -> None:
    """Record (or refresh) a lake in the registry, self-healing its path.

    ``required=False`` (the default, used by path resolution) makes this advisory: the
    registry is bookkeeping about *where* the lake is, so failing to update it must never
    fail the caller's actual work. ``required=True`` is for the explicit
    adopt/activate/forget commands, where persisting the choice *is* the job.
    """
    reg = registry()
    known = [e for e in reg["known"] if isinstance(e, dict)]
    entry = next((e for e in known if e.get("lake_id") == stamp.lake_id), None)
    now = datetime.now(timezone.utc)

    # Skip the write entirely when nothing material changed. resolve_root() runs on every
    # parquet write, so without this the registry is rewritten thousands of times per
    # download — pure churn, and every one of those writes is a chance to race.
    if entry is not None and not make_active:
        unchanged = (
            entry.get("last_path") == str(root)
            and entry.get("label") == stamp.label
            and (not volume_uuid or entry.get("volume_uuid") == volume_uuid)
        )
        if unchanged:
            try:
                seen = datetime.fromisoformat(str(entry.get("last_seen") or ""))
            except ValueError:
                seen = None
            # Refresh last_seen at most hourly; it is a diagnostic, not a guarantee.
            if seen is not None and (now - seen).total_seconds() < 3600:
                return

    if entry is None:
        entry = {"lake_id": stamp.lake_id}
        known.append(entry)
    entry.update(
        label=stamp.label,
        last_path=str(root),
        last_seen=now.isoformat(timespec="seconds"),
    )
    # Only overwrite a known volume_uuid when we actually learned one.
    if volume_uuid:
        entry["volume_uuid"] = volume_uuid
    entry.setdefault("volume_uuid", "")
    reg["known"] = known
    if make_active or not reg.get("active_lake_id"):
        reg["active_lake_id"] = stamp.lake_id
    try:
        _write_registry(reg)
    except OSError:
        if required:
            raise


# ─── Volume enumeration ──────────────────────────────────────────────────────
def _mounts() -> list[tuple[str, str, str]]:
    """Return [(mountpoint, fstype, device)] for plausible real filesystems."""
    out: list[tuple[str, str, str]] = []
    try:
        raw = Path("/proc/mounts").read_text().splitlines()
    except OSError:  # pragma: no cover - non-Linux
        return out
    for line in raw:
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mnt, fstype = parts[0], parts[1], parts[2]
        if fstype not in _REAL_FSTYPES:
            continue
        # /proc/mounts octal-escapes spaces and friends.
        mnt = mnt.encode().decode("unicode_escape")
        if any(mnt == p or mnt.startswith(p + "/") for p in _SKIP_MOUNT_PREFIXES):
            continue
        out.append((mnt, fstype, device))
    return out


def _by_uuid_map() -> dict[str, str]:
    """Map filesystem UUID -> device path, from /dev/disk/by-uuid."""
    result: dict[str, str] = {}
    d = Path("/dev/disk/by-uuid")
    try:
        entries = list(d.iterdir())
    except OSError:
        return result
    for link in entries:
        try:
            result[link.name] = str(link.resolve())
        except OSError:
            continue
    return result


def _device_uuid(device: str) -> str:
    for fs_uuid, dev in _by_uuid_map().items():
        if dev == device:
            return fs_uuid
    return ""


def _is_removable(device: str) -> bool:
    """Best-effort: consult /sys/block/<disk>/removable for the parent disk."""
    name = Path(device).name  # e.g. sda1
    if not name:
        return False
    base = name.rstrip("0123456789")
    if name.startswith("nvme"):  # nvme0n1p3 -> nvme0n1
        base = name.split("p")[0]
    if name.startswith("mmcblk"):  # mmcblk0p1 -> mmcblk0
        base = name.split("p")[0]
        return True  # SD/eMMC cards are removable media in practice
    try:
        return Path(f"/sys/block/{base}/removable").read_text().strip() == "1"
    except OSError:
        return False


def _find_stamp_at_or_below(mount: Path, *, depth: int = 1) -> tuple[Path, LakeStamp] | None:
    """Look for a stamped lake at ``mount`` or up to ``depth`` levels beneath it."""
    stamp = LakeStamp.read(mount)
    if stamp:
        return mount, stamp
    if depth <= 0:
        return None
    try:
        children = sorted(p for p in mount.iterdir() if p.is_dir())
    except OSError:
        return None
    for child in children:
        if child.name in {"lost+found", ".Trash-1000", "System Volume Information"}:
            continue
        found = _find_stamp_at_or_below(child, depth=depth - 1)
        if found:
            return found
    return None


def list_volumes(*, scan_lakes: bool = True) -> list[VolumeInfo]:
    """Enumerate mounted volumes that could host a lake, newest-useful first.

    Never raises: an unreadable mount is reported with zeroed capacity rather than
    aborting the scan.
    """
    uuid_map = {dev: u for u, dev in _by_uuid_map().items()}
    vols: list[VolumeInfo] = []
    for mnt, fstype, device in _mounts():
        p = Path(mnt)
        try:
            usage = shutil.disk_usage(p)
            total, free = usage.total, usage.free
        except OSError:
            total, free = 0, 0
        info = VolumeInfo(
            path=str(p),
            fstype=fstype,
            device=device,
            total_bytes=total,
            free_bytes=free,
            writable=os.access(p, os.W_OK | os.X_OK),
            removable=_is_removable(device),
            volume_uuid=uuid_map.get(device, ""),
            label=p.name if p != Path("/") else "system",
        )
        if scan_lakes:
            # Go deeper on removable media: users nest lakes inside a project folder on
            # a USB drive far more often than they do on the system disk, where a deep
            # scan would also be needlessly slow.
            found = _find_stamp_at_or_below(p, depth=2 if info.removable else 1)
            if found:
                root, stamp = found
                info.lake_at = str(root)
                info.lake_id = stamp.lake_id
                info.lake_label = stamp.label
        vols.append(info)
    # Removable volumes with a lake first, then most free space.
    vols.sort(key=lambda v: (not bool(v.lake_at), not v.removable, -v.free_bytes))
    return vols


# ─── Resolution ──────────────────────────────────────────────────────────────
def _candidate_paths_for(entry: dict[str, Any]) -> Iterable[Path]:
    """Places a previously-known lake might be right now, cheapest guess first."""
    last = entry.get("last_path")
    if last:
        yield Path(last)
    vol_uuid = entry.get("volume_uuid")
    if vol_uuid:
        # The drive may have remounted at a different path: find its device, then the
        # mountpoint that device currently occupies, then the same relative subpath.
        dev = _by_uuid_map().get(vol_uuid, "")
        if dev:
            rel = ""
            if last:
                for mnt, _fs, d in _mounts():
                    if d == dev and str(last).startswith(mnt):
                        rel = str(Path(last).relative_to(mnt))
                        break
            for mnt, _fs, d in _mounts():
                if d != dev:
                    continue
                yield Path(mnt) / rel if rel and rel != "." else Path(mnt)
    if last:
        # The folder may have been renamed or moved alongside where it used to be
        # (a very common manual reorganisation). Scanning one directory is cheap.
        parent = Path(last).parent
        try:
            siblings = sorted(p for p in parent.iterdir() if p.is_dir())
        except OSError:
            siblings = []
        for sib in siblings:
            yield sib


def _verify(root: Path, expect_lake_id: str = "") -> LakeStamp | None:
    """Return the stamp if ``root`` holds a readable lake matching the expectation."""
    stamp = LakeStamp.read(root)
    if stamp is None:
        return None
    if expect_lake_id and stamp.lake_id != expect_lake_id:
        return None
    return stamp


def _resolve(explicit: str | Path | None = None) -> tuple[Path, LakeStamp] | None:
    """Best-effort resolution. Returns None instead of raising when not found."""
    # 1. An explicit argument or KITELAKE_ROOT always wins, and is allowed to point at
    #    an unstamped directory (tests and first-time setup rely on this).
    raw = explicit if explicit is not None else os.environ.get("KITELAKE_ROOT")
    if raw:
        root = Path(raw).expanduser()
        stamp = LakeStamp.read(root)
        if stamp is None and root.is_dir():
            stamp = LakeStamp.new(label=root.name)
            try:
                ensure_layout(root)
                stamp.write(root)
            except OSError:
                # Read-only target: still usable for reads, just not stampable.
                return root, stamp
        if stamp is not None:
            return root, stamp
        return None

    reg = registry()
    known = [e for e in reg["known"] if isinstance(e, dict)]
    active_id = reg.get("active_lake_id") or ""
    ordered = sorted(known, key=lambda e: e.get("lake_id") != active_id)

    # 2. Try the known entries at their last path, then via their volume UUID.
    for entry in ordered:
        want = str(entry.get("lake_id") or "")
        for cand in _candidate_paths_for(entry):
            stamp = _verify(cand, want)
            if stamp:
                _remember(stamp, cand, volume_uuid=str(entry.get("volume_uuid") or ""))
                return cand, stamp

    # 3. Nothing where we left it — sweep every mounted volume for the stamp.
    for vol in list_volumes(scan_lakes=True):
        if not vol.lake_at:
            continue
        if active_id and vol.lake_id != active_id and known:
            continue  # prefer the active lake; unknown ones are handled below
        root = Path(vol.lake_at)
        stamp = _verify(root, vol.lake_id)
        if stamp:
            _remember(stamp, root, volume_uuid=vol.volume_uuid)
            return root, stamp

    # 4. Last resort: adopt any single stamped lake we can see, even if unknown.
    seen = [v for v in list_volumes(scan_lakes=True) if v.lake_at]
    if len(seen) == 1:
        root = Path(seen[0].lake_at)
        stamp = _verify(root)
        if stamp:
            _remember(stamp, root, volume_uuid=seen[0].volume_uuid)
            return root, stamp
    return None


def resolve_root(explicit: str | Path | None = None) -> Path:
    """Return the active lake root.

    Raises:
        LakeUnavailable: carrying :attr:`~LakeUnavailable.guidance` for the UI. Callers
            that render to a human should prefer :func:`lake_status`, which never raises.
    """
    found = _resolve(explicit)
    if found:
        return found[0]
    status = lake_status()
    raise LakeUnavailable("\n".join([status.reason, *status.guidance]), guidance=status.to_dict())


def lake_status(explicit: str | Path | None = None) -> LakeStatus:
    """Describe the lake's reachability. **Never raises.**

    This is the function a UI should call. When ``available`` is False the returned
    object explains why in plain sentences and lists usable volumes to pick from.
    """
    try:
        volumes = list_volumes(scan_lakes=True)
    except Exception:  # pragma: no cover - defensive; scanning must never break status
        volumes = []
    # Include drives that already hold a lake even when their root is not writable: a
    # root-owned mount point (normal on a freshly formatted USB stick) does not stop us
    # reopening a lake that already exists inside it. Filtering those out hid the very
    # drive the user was trying to pick.
    candidates = [
        v.to_dict()
        for v in volumes
        if (v.writable or v.lake_at) and v.free_bytes > 2**30
    ]
    reg = registry()
    known = [e for e in reg["known"] if isinstance(e, dict)]

    try:
        found = _resolve(explicit)
    except Exception as exc:  # pragma: no cover - defensive
        found = None
        reason = f"Unexpected problem while locating the data folder: {exc}"
    else:
        reason = ""

    if found:
        root, stamp = found
        try:
            usage = shutil.disk_usage(root)
            total, free = usage.total, usage.free
        except OSError:
            total, free = 0, 0
        return LakeStatus(
            available=True,
            root=str(root),
            lake_id=stamp.lake_id,
            label=stamp.label,
            free_bytes=free,
            total_bytes=total,
            candidates=candidates,
            known=known,
        )

    # Not found — work out the most useful explanation we can.
    active_id = reg.get("active_lake_id") or ""
    entry = next((e for e in known if e.get("lake_id") == active_id), None) or (
        known[0] if known else None
    )
    last_path = str((entry or {}).get("last_path") or "")
    vol_uuid = str((entry or {}).get("volume_uuid") or "")
    label = str((entry or {}).get("label") or "")

    present_unmounted = False
    if vol_uuid:
        dev = _by_uuid_map().get(vol_uuid, "")
        if dev:
            mounted = {d for _m, _f, d in _mounts()}
            present_unmounted = dev not in mounted

    guidance: list[str] = []
    if entry is None:
        reason = "No data folder has been set up yet."
        guidance.append(
            "Choose where the market data should live — pick a folder on your USB drive "
            "or any volume with free space."
        )
        guidance.append("Run `kitelake root --pick` for a graphical folder chooser.")
    elif present_unmounted:
        reason = (
            f"The drive holding '{label or 'the data folder'}' is connected but not mounted."
        )
        guidance.append(
            "Open Files (or your file manager) and click the drive once to mount it, then retry."
        )
        guidance.append(f"It was last used at: {last_path}")
    else:
        reason = f"The data folder '{label or last_path}' is not reachable right now."
        guidance.append(
            "If it is on a USB drive, plug the drive back in — it will be found "
            "automatically even if it mounts to a different path."
        )
        guidance.append(f"Last seen at: {last_path}" if last_path else "No previous path recorded.")
        guidance.append("Or choose a different folder: `kitelake root --pick`.")

    if candidates:
        top = candidates[0]
        guidance.append(
            f"Writable volumes available now: "
            + ", ".join(f"{c['path']} ({c['free_gib']} GiB free)" for c in candidates[:4])
        )
        guidance.append(f"Suggested location: {top['path']}/{DEFAULT_LAKE_DIRNAME}")
    else:
        guidance.append("No writable volume with at least 1 GiB free was detected.")

    guidance.append("Reads and downloads are paused until a folder is available — nothing is lost.")

    return LakeStatus(
        available=False,
        reason=reason,
        guidance=guidance,
        last_path=last_path,
        volume_uuid=vol_uuid,
        label=label,
        volume_present_unmounted=present_unmounted,
        candidates=candidates,
        known=known,
    )


# ─── Mutation: adopt / forget / activate ─────────────────────────────────────
def ensure_layout(root: Path) -> Path:
    """Create the lake's subdirectories. Idempotent."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for sub in SUBDIRS:
        (root / sub).mkdir(exist_ok=True)
    return root


def adopt_root(
    path: str | Path, *, label: str = "", make_active: bool = True, create: bool = True
) -> LakeStatus:
    """Point kitelake at ``path``, stamping and registering it.

    If ``path`` already holds a stamped lake, that identity is preserved (re-adopting a
    drive must not orphan its data). Otherwise a new stamp is minted.

    Raises:
        LakeUnavailable: if the path cannot be created or written to — with guidance
            that names the actual OS error, e.g. a root-owned mount point.
    """
    root = Path(path).expanduser()
    if create:
        try:
            ensure_layout(root)
        except OSError as exc:
            hint = ""
            # The common case on a freshly-formatted removable drive: the filesystem
            # root belongs to root, so the desktop user cannot create a directory.
            if isinstance(exc, PermissionError):
                parent = root.parent if root.parent.exists() else root
                hint = (
                    f"\n\nThe folder is not writable by your user. Grant it once with:\n"
                    f'    sudo install -d -o "$USER" -g "$USER" -m 755 "{root}"'
                    f"\n\n(parent: {parent})"
                )
            raise LakeUnavailable(
                f"Cannot use {root}: {exc.strerror or exc}{hint}",
                guidance={"path": str(root), "error": str(exc)},
            ) from exc
    if not root.is_dir():
        raise LakeUnavailable(
            f"{root} does not exist and was not created.",
            guidance={"path": str(root)},
        )
    if not os.access(root, os.W_OK | os.X_OK):
        raise LakeUnavailable(
            f"{root} exists but is not writable by your user.\n"
            f'Grant it once with:\n    sudo install -d -o "$USER" -g "$USER" -m 755 "{root}"',
            guidance={"path": str(root)},
        )

    stamp = LakeStamp.read(root)
    if stamp is None:
        stamp = LakeStamp.new(label=label or f"{root.name}")
        stamp.write(root)
    elif label and label != stamp.label:
        stamp = LakeStamp(
            lake_id=stamp.lake_id,
            label=label,
            created_at=stamp.created_at,
            schema_version=stamp.schema_version,
        )
        stamp.write(root)

    # Record the volume UUID so the lake is findable after a remount.
    vol_uuid = ""
    best = ""
    for mnt, _fs, device in _mounts():
        if str(root) == mnt or str(root).startswith(mnt.rstrip("/") + "/"):
            if len(mnt) > len(best):  # deepest matching mount wins
                best, vol_uuid = mnt, _device_uuid(device)
    # required=True: persisting the user's explicit choice IS the job here, so a failed
    # registry write must surface rather than be swallowed like the advisory hot-path one.
    _remember(stamp, root, volume_uuid=vol_uuid, make_active=make_active, required=True)
    return lake_status()


def forget_root(lake_id: str) -> LakeStatus:
    """Remove a lake from the registry. The data itself is never touched."""
    reg = registry()
    reg["known"] = [e for e in reg["known"] if e.get("lake_id") != lake_id]
    if reg.get("active_lake_id") == lake_id:
        reg["active_lake_id"] = reg["known"][0]["lake_id"] if reg["known"] else ""
    _write_registry(reg)
    return lake_status()


def set_active(lake_id: str) -> LakeStatus:
    """Make a known lake the active one."""
    reg = registry()
    if not any(e.get("lake_id") == lake_id for e in reg["known"]):
        raise LakeUnavailable(f"Unknown lake id {lake_id!r}. Use `kitelake root --list`.")
    reg["active_lake_id"] = lake_id
    _write_registry(reg)
    return lake_status()


# ─── Directory browsing (for the graphical picker) ────────────────────────────
def browse(path: str | Path | None = None, *, show_hidden: bool = False) -> dict[str, Any]:
    """List directories under ``path`` for a folder-picker UI. Never raises.

    Returns a dict with ``path``, ``parent``, ``entries`` (directories only, since the
    user is choosing a folder), plus capacity info and whether the location is writable.
    """
    target = Path(path).expanduser() if path else Path.home()
    result: dict[str, Any] = {
        "path": str(target),
        "parent": str(target.parent) if target != target.parent else "",
        "entries": [],
        "writable": False,
        "error": "",
        "free_gib": 0.0,
        "has_lake": False,
        "lake_label": "",
    }
    if not target.is_dir():
        result["error"] = f"{target} is not a folder."
        result["path"] = str(Path.home())
        target = Path.home()
    try:
        result["writable"] = os.access(target, os.W_OK | os.X_OK)
        usage = shutil.disk_usage(target)
        result["free_gib"] = round(usage.free / 2**30, 2)
    except OSError:
        pass
    stamp = LakeStamp.read(target)
    if stamp:
        result["has_lake"] = True
        result["lake_label"] = stamp.label
    entries = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if not show_hidden and child.name.startswith("."):
                continue
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue
            child_stamp = LakeStamp.read(child)
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "writable": os.access(child, os.W_OK | os.X_OK),
                    "has_lake": child_stamp is not None,
                    "lake_label": child_stamp.label if child_stamp else "",
                }
            )
    except PermissionError:
        result["error"] = f"No permission to list {target}."
    except OSError as exc:
        result["error"] = f"Cannot list {target}: {exc.strerror or exc}"
    result["entries"] = entries
    return result


def pick_directory_gui(initial: str | Path | None = None) -> str:
    """Open a native folder chooser. Returns "" if cancelled or unavailable.

    Tries zenity (GNOME/Wayland-friendly), then kdialog, then tkinter. Used by
    ``kitelake root --pick``; the web UI has its own picker via :func:`browse`.
    """
    import subprocess

    start = str(Path(initial).expanduser()) if initial else str(Path.home())
    for argv in (
        ["zenity", "--file-selection", "--directory", "--title=Choose the market-data folder",
         f"--filename={start}/"],
        ["kdialog", "--getexistingdirectory", start],
    ):
        exe = shutil.which(argv[0])
        if not exe:
            continue
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
        return ""  # user cancelled
    try:  # pragma: no cover - GUI
        import tkinter
        from tkinter import filedialog

        rootw = tkinter.Tk()
        rootw.withdraw()
        chosen = filedialog.askdirectory(initialdir=start, title="Choose the market-data folder")
        rootw.destroy()
        return chosen or ""
    except Exception:
        return ""


# ─── Path accessors (resolve at call time, never cached at import) ────────────
def _sub(name: str, explicit: str | Path | None = None, *, create: bool = True) -> Path:
    root = resolve_root(explicit)
    path = root / name
    if create:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LakeUnavailable(
                f"The data folder {root} became unwritable: {exc.strerror or exc}",
                guidance=lake_status().to_dict(),
            ) from exc
    return path


def bars_dir(explicit: str | Path | None = None, *, create: bool = True) -> Path:
    return _sub("bars", explicit, create=create)


def instruments_dir(explicit: str | Path | None = None, *, create: bool = True) -> Path:
    return _sub("instruments", explicit, create=create)


def manifest_dir(explicit: str | Path | None = None, *, create: bool = True) -> Path:
    return _sub("manifest", explicit, create=create)


def catalog_dir(explicit: str | Path | None = None, *, create: bool = True) -> Path:
    return _sub("catalog", explicit, create=create)


def logs_dir(explicit: str | Path | None = None, *, create: bool = True) -> Path:
    return _sub("logs", explicit, create=create)


def staging_dir(explicit: str | Path | None = None, *, create: bool = True) -> Path:
    return _sub("_staging", explicit, create=create)


def ticks_dir(explicit: str | Path | None = None, *, create: bool = True) -> Path:
    return _sub("ticks", explicit, create=create)
