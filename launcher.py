"""Kaiwa desktop entry point — starts the bundled web server and opens a tab.

This is the script PyInstaller freezes into the double-click app. The AI
backends (Ollama, VOICEVOX, AivisSpeech) are optional and discovered at runtime
by the app itself; the onboarding wizard walks the user through AI setup on
first launch. This launcher only owns starting the server and opening a browser.
"""
import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser

PORT = int(os.environ.get("KAIWA_PORT", "8130"))


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
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    import uvicorn
    from server.main import app
    # 0.0.0.0 so a phone on the same network / Tailscale can reach it too.
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
