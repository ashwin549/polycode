"""
Safe edit pipeline — staging, snapshots, and undo.

Directory layout inside the project:
    .polycode/
        staging/          ← modified content, mirroring real paths
        snapshots/
            20240404_153201/   ← one folder per apply action
                path/to/file.py    ← original before it was changed

Public API
----------
stage_edit(cwd, path, modified)   → write modified content to staging
snapshot_file(cwd, path)          → copy original into latest snapshot folder
apply_staged(cwd, path)           → move staged file over the real file
apply_all_staged(cwd)             → apply every file currently in staging
undo_latest(cwd)                  → restore all files from the newest snapshot
pending_paths(cwd)                → list of paths currently staged
clear_staging(cwd)                → wipe the staging area
"""

import shutil
from datetime import datetime
from pathlib import Path


# ── helpers ───────────────────────────────────────────────────────────────────

def _staging_dir(cwd: Path) -> Path:
    return cwd / ".polycode" / "staging"

def _snapshots_dir(cwd: Path) -> Path:
    return cwd / ".polycode" / "snapshots"

def _staged_path(cwd: Path, path: str) -> Path:
    """Where a staged version of `path` lives."""
    return _staging_dir(cwd) / path

def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── active snapshot folder for this session ───────────────────────────────────
# One timestamp folder is created per apply action so each apply is undoable
# independently. We keep the current one in module state.

_current_snapshot: Path | None = None

def _new_snapshot_folder(cwd: Path) -> Path:
    global _current_snapshot
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = _ensure(_snapshots_dir(cwd) / ts)
    _current_snapshot = folder
    return folder

def _active_snapshot(cwd: Path) -> Path:
    """Return the current snapshot folder, creating one if needed."""
    global _current_snapshot
    if _current_snapshot is None:
        _current_snapshot = _new_snapshot_folder(cwd)
    return _current_snapshot

def reset_snapshot_session():
    """Call this before each apply batch so undo covers exactly that batch."""
    global _current_snapshot
    _current_snapshot = None


# ── public API ────────────────────────────────────────────────────────────────

def stage_edit(cwd: Path, path: str, modified_content: str) -> Path:
    """
    Write modified_content to the staging area.
    Does NOT touch the real file.
    Returns the staging path.
    """
    staged = _staged_path(cwd, path)
    _ensure(staged.parent)
    staged.write_text(modified_content, encoding="utf-8")
    return staged


def snapshot_file(cwd: Path, path: str) -> Path | None:
    """
    Copy the current real file into the active snapshot folder.
    Returns the snapshot path, or None if the real file doesn't exist.
    """
    real = cwd / path
    if not real.exists():
        return None
    snap_path = _active_snapshot(cwd) / path
    _ensure(snap_path.parent)
    shutil.copy2(real, snap_path)
    return snap_path


def apply_staged(cwd: Path, path: str) -> bool:
    """
    Move the staged version of `path` over the real file.
    Returns True if successful.
    """
    staged = _staged_path(cwd, path)
    if not staged.exists():
        return False
    real = cwd / path
    _ensure(real.parent)
    shutil.move(str(staged), real)
    return True


def apply_all_staged(cwd: Path) -> list[str]:
    """
    Apply every file currently in staging.
    Returns list of applied paths.
    """
    staging = _staging_dir(cwd)
    if not staging.exists():
        return []
    applied = []
    for staged_file in staging.rglob("*"):
        if staged_file.is_file():
            rel = str(staged_file.relative_to(staging))
            if apply_staged(cwd, rel):
                applied.append(rel)
    return applied


def pending_paths(cwd: Path) -> list[str]:
    """Return relative paths of all files currently in staging."""
    staging = _staging_dir(cwd)
    if not staging.exists():
        return []
    return [
        str(f.relative_to(staging))
        for f in staging.rglob("*")
        if f.is_file()
    ]


def clear_staging(cwd: Path):
    """Wipe the staging area without applying."""
    staging = _staging_dir(cwd)
    if staging.exists():
        shutil.rmtree(staging)


def undo_latest(cwd: Path) -> list[str] | None:
    """
    Restore all files from the most recent snapshot.
    Returns list of restored paths, or None if no snapshots exist.
    """
    snapshots = _snapshots_dir(cwd)
    if not snapshots.exists():
        return None

    # Most recent folder by name (timestamps sort lexicographically)
    folders = sorted(
        [f for f in snapshots.iterdir() if f.is_dir()],
        reverse=True,
    )
    if not folders:
        return None

    latest = folders[0]
    restored = []

    for snap_file in latest.rglob("*"):
        if snap_file.is_file():
            rel = str(snap_file.relative_to(latest))
            real = cwd / rel
            _ensure(real.parent)
            shutil.copy2(snap_file, real)
            restored.append(rel)

    # Remove the snapshot we just consumed so the next /undo goes one further back
    shutil.rmtree(latest)
    return restored