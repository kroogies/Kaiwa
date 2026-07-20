"""Filesystem locations for Kaiwa.

In development (running from a git checkout) everything lives under the repo:
read-only resources and the writable ``data/`` sit side by side, exactly as
before. When the app is packaged with PyInstaller and installed, the bundle is
read-only, so writable state — the SQLite DB, TTS cache, built dictionary, and
any downloaded models — moves to a per-user data directory instead. Read-only
resources (the web UI and anything bundled) stay inside the app.

Every module resolves its paths through here so the two modes stay consistent.
"""
import os
import sys

FROZEN = getattr(sys, "frozen", False)


def _bundle_root() -> str:
    """Directory holding bundled, read-only resources (web/, vendor/, …)."""
    if FROZEN:
        # PyInstaller unpacks bundled data to _MEIPASS (onefile) or leaves it
        # next to the executable (onedir); _MEIPASS covers both.
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _user_data_dir() -> str:
    """Per-user, writable directory for an installed app."""
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "Kaiwa")


# Read-only resources shipped with the app.
APP_ROOT = _bundle_root()
WEB_DIR = os.path.join(APP_ROOT, "web")

# Writable per-user state. In dev this stays inside the repo so nothing changes.
DATA_DIR = _user_data_dir() if FROZEN else os.path.join(APP_ROOT, "data")

# Large models (whisper weights, JMdict source) are NOT shipped in the installer;
# they download next to the writable data on first use. In dev they sit in the
# repo's models/ as before.
MODELS_DIR = os.path.join(DATA_DIR, "models") if FROZEN else os.path.join(APP_ROOT, "models")

# Read-only resources bundled inside the installed app (whisper binary, JMdict
# source). In dev these are the repo's own vendor/ and models/ folders.
VENDOR_DIR = os.path.join(APP_ROOT, "vendor")
BUNDLED_MODELS_DIR = os.path.join(APP_ROOT, "models")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)


# --- PATH / subprocess environment for the frozen, Finder-launched app --------
# A GUI app launched from Finder/Explorer inherits a minimal PATH that omits
# Homebrew (and other common) locations, so CLI helpers like whisper-cli or
# tailscale can't be found. Put those directories back for the frozen app.
if FROZEN and sys.platform == "darwin":
    _existing = os.environ.get("PATH", "").split(os.pathsep)
    _brew = [p for p in ("/opt/homebrew/bin", "/usr/local/bin") if p not in _existing]
    if _brew:
        os.environ["PATH"] = os.pathsep.join([*_brew, *filter(None, _existing)])


def system_env() -> dict:
    """Environment for spawning OS binaries (say, afconvert, powershell, …).

    PyInstaller injects DYLD_LIBRARY_PATH / DYLD_FRAMEWORK_PATH (macOS) and
    LD_LIBRARY_PATH (Linux) pointing at the bundle so our own libraries load. A
    system binary spawned as a subprocess inherits those and can crash loading
    incompatible libraries. PyInstaller stashes the originals in *_ORIG — restore
    those (or drop the var entirely) so system tools run in a clean environment.
    """
    env = dict(os.environ)
    for var in ("DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "LD_LIBRARY_PATH"):
        orig = env.pop(var + "_ORIG", None)
        if orig is not None:
            env[var] = orig
        else:
            env.pop(var, None)
    return env
