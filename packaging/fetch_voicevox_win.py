"""Download + trim the VOICEVOX Windows CPU engine into vendor/voicevox (CI only).

Best-effort: the engine is a ~1.7 GB 7-Zip archive, so CI wraps this so it can
never fail the build — if it's skipped, Windows just falls back to SAPI voices.
Reuses the trim logic in stage_voicevox.py so both platforms keep the same voices.
"""
import os
import subprocess
import sys
import tempfile

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stage_voicevox import ROOT, stage  # noqa: E402

# Pinned to the same engine version as the bundled macOS build (matching .vvm names).
URL = ("https://github.com/VOICEVOX/voicevox_engine/releases/download/"
       "0.25.2/voicevox_engine-windows-cpu-0.25.2.7z.001")
DEST = os.path.join(ROOT, "vendor", "voicevox")


def main() -> None:
    tmp = tempfile.mkdtemp()
    archive = os.path.join(tmp, "vv.7z.001")
    print("downloading VOICEVOX windows engine (~1.7 GB)…")
    with requests.get(URL, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(archive, "wb") as f:
            for block in r.iter_content(chunk_size=1 << 20):
                f.write(block)
    extract = os.path.join(tmp, "engine")
    subprocess.run(["7z", "x", archive, f"-o{extract}", "-y"], check=True)
    src = next((root for root, _, files in os.walk(extract) if "run.exe" in files), None)
    if not src:
        raise RuntimeError("run.exe not found in extracted VOICEVOX engine")
    stage(src, DEST)
    print("staged trimmed VOICEVOX (windows) into", DEST)


if __name__ == "__main__":
    main()
