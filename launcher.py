"""Kaiwa desktop entry point — starts the bundled web server and opens a tab.

This is the script PyInstaller freezes into the double-click app. The AI
backends (Ollama, VOICEVOX, AivisSpeech) are optional and discovered at runtime
by the app itself; the onboarding wizard walks the user through AI setup on
first launch. This launcher only owns starting the server and opening a browser.
"""
import atexit
import multiprocessing
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

PORT = int(os.environ.get("KAIWA_PORT", "8130"))
VOICEVOX_PORT = 50021


def _redirect_output_when_headless() -> None:
    """A windowed PyInstaller build has no console, so sys.stdout/sys.stderr are
    None. Anything that touches them crashes — notably uvicorn's log formatter
    calls sys.stdout.isatty() at startup. Point both at a log file in the user's
    data dir so logging works and we get a crash trail to debug from.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return  # normal console / dev run — leave streams alone
    try:
        from server.paths import DATA_DIR
        log_path = os.path.join(DATA_DIR, "kaiwa.log")
    except Exception:
        log_path = os.path.join(os.path.expanduser("~"), "kaiwa.log")
    log = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log


def _server_up(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _clear_quarantine(path: str) -> None:
    """A downloaded .app is quarantined; macOS then refuses to launch the nested
    helper binaries (whisper, the VOICEVOX engine) until the flag is cleared.
    The main app was already approved by the user, so clear its own bundled
    tools. Best-effort — a no-op when nothing is quarantined."""
    if sys.platform == "darwin" and os.path.isdir(path):
        subprocess.run(["xattr", "-dr", "com.apple.quarantine", path],
                       capture_output=True)


def _start_voicevox() -> None:
    """Start the bundled VOICEVOX TTS engine if present and not already running.

    The engine is a VOICEVOX-protocol server on :50021 (~20s boot); tts.py picks
    it up automatically once it answers. Absent in a dev checkout (run.sh starts
    it there) and when the engine wasn't bundled for this platform."""
    from server import paths
    engine_dir = os.path.join(paths.VENDOR_DIR, "voicevox")
    exe = os.path.join(engine_dir, "run.exe" if os.name == "nt" else "run")
    if not os.path.exists(exe) or _server_up(VOICEVOX_PORT):
        return
    _clear_quarantine(engine_dir)
    try:
        os.chmod(exe, os.stat(exe).st_mode | 0o111)
    except OSError:
        pass
    try:
        # The engine resolves its models/resources relative to its own directory.
        proc = subprocess.Popen(
            [exe, "--host", "127.0.0.1", "--port", str(VOICEVOX_PORT)],
            cwd=engine_dir, env=paths.system_env(),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        atexit.register(lambda: proc.terminate())
    except Exception:
        pass


def _open_browser_when_ready() -> None:
    # A cold first start (imports + DB init) can take a while on slow machines.
    for _ in range(120):
        if _server_up(PORT):
            webbrowser.open(f"http://localhost:{PORT}")
            return
        time.sleep(0.5)


def main() -> None:
    multiprocessing.freeze_support()  # required for frozen apps that may spawn
    _redirect_output_when_headless()
    if _server_up(PORT):
        # Already running (double-launch) — just focus a tab and exit.
        webbrowser.open(f"http://localhost:{PORT}")
        return
    from server import paths
    _clear_quarantine(paths.VENDOR_DIR)  # un-quarantine bundled whisper + voicevox helpers
    threading.Thread(target=_start_voicevox, daemon=True).start()  # ~20s boot, don't block
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    import uvicorn
    from server.main import app
    # 0.0.0.0 so a phone on the same network / Tailscale can reach it too.
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
