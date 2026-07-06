"""Backup, export and restore of user data.

Everything worth keeping (streak, saved words, sessions, mistakes, settings)
lives in one SQLite file, so backup = a consistent snapshot of data/kaiwa.db.
Snapshots use the SQLite backup API, so they're safe while the app is writing.
"""
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from datetime import datetime

from . import db

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Kaiwa Backups")
KEEP = 8  # rotated copies to keep


def backup_dir() -> str:
    return db.get_setting("backup_dir") or DEFAULT_DIR


def snapshot_to(path: str):
    """Write a consistent snapshot of the live db to `path`."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    src = sqlite3.connect(db.DB_PATH)
    try:
        dst = sqlite3.connect(path)
        with dst:
            src.backup(dst)
        dst.close()
    finally:
        src.close()


def export_snapshot() -> str:
    """Snapshot into a temp file for download; caller deletes after serving."""
    fd, tmp = tempfile.mkstemp(suffix=".db", prefix="kaiwa-export-")
    os.close(fd)
    snapshot_to(tmp)
    return tmp


def backup_now() -> dict:
    d = backup_dir()
    path = os.path.join(d, f"kaiwa-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
    snapshot_to(path)
    # rotate oldest copies out
    files = sorted(f for f in os.listdir(d) if f.startswith("kaiwa-") and f.endswith(".db"))
    for f in files[:-KEEP]:
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass
    db.set_settings({"backup_last": time.time()})
    return {"ok": True, "path": path, "last": time.time()}


def restore_from(data: bytes) -> str | None:
    """Validate an uploaded backup and swap it in. Returns an error string or None."""
    if not data.startswith(b"SQLite format 3\x00"):
        return "That file doesn't look like a Kaiwa backup (.db file)"
    fd, tmp = tempfile.mkstemp(suffix=".db", prefix="kaiwa-restore-")
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        con = sqlite3.connect(tmp)
        try:
            names = {r[0] for r in
                     con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
        if not {"profile", "sessions", "vocab"} <= names:
            return "That database is missing Kaiwa's tables — is it really a Kaiwa backup?"
        snapshot_to(db.DB_PATH + ".pre-restore")  # safety copy of what's being replaced
        shutil.move(tmp, db.DB_PATH)
        _sanitize_cross_platform()
        return None
    except Exception as e:  # noqa: BLE001 — surfaced to the user
        return f"Restore failed: {e}"
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _sanitize_cross_platform():
    """A backup made on another OS can carry settings that don't work here:
    a TTS voice for an engine this platform doesn't have (macOS `say:` voices
    on Windows) or an absolute backup path from the other filesystem. Reset
    those to defaults rather than let them fail quietly later.

    Deliberately does NOT touch `vv:` voices — VOICEVOX runs on every
    platform and may simply be down at restore time.
    """
    fixes = {}
    voice = db.get_setting("voice") or ""
    if voice and not (voice.startswith("vv:")
                      or (voice.startswith("say:") and shutil.which("say"))):
        fixes["voice"] = ""  # falls back to tts.default_voice()
    d = db.get_setting("backup_dir") or ""
    if d and not os.path.isdir(d) and not os.path.isdir(os.path.dirname(d)):
        fixes["backup_dir"] = ""  # foreign path — falls back to DEFAULT_DIR
    if fixes:
        db.set_settings(fixes)


def reset_all():
    """Wipe all user data back to a fresh install (for debugging / starting over).

    Keeps a safety snapshot next to the db, same as restore does, so a
    mis-click is recoverable by renaming kaiwa.db.pre-reset back.
    """
    snapshot_to(db.DB_PATH + ".pre-reset")
    os.remove(db.DB_PATH)
    db.init()


def _maybe_backup():
    freq = db.get_setting("backup_freq", "off")
    if freq not in ("daily", "weekly"):
        return
    interval = 86400 if freq == "daily" else 7 * 86400
    last = float(db.get_setting("backup_last", 0) or 0)
    if time.time() - last >= interval:
        backup_now()


def start_scheduler():
    """Hourly check in a daemon thread — cheap, and survives laptop sleep fine."""
    def loop():
        while True:
            try:
                _maybe_backup()
            except Exception:
                pass  # never let backup errors take the app down
            time.sleep(3600)
    threading.Thread(target=loop, daemon=True, name="kaiwa-backup").start()
