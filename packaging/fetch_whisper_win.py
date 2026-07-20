"""Download a prebuilt whisper.cpp CLI (Windows x64) into vendor/whisper/.

Windows-only. The zip ships whisper-cli.exe alongside its ggml DLLs; Windows
resolves sibling DLLs from the executable's own directory, so a flat extract is
self-contained (no dylib relocation, unlike macOS — see stage_whisper.sh).
stt.py finds the binary under vendor/whisper/ (and a nested Release/ if present).
"""
import io
import os
import zipfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "vendor", "whisper")
API = "https://api.github.com/repos/ggml-org/whisper.cpp/releases/latest"
ASSET = "whisper-bin-x64.zip"  # plain CPU build (BLAS/cuBLAS variants are far larger)
# Fallback when the API is unauthenticated + rate-limited (e.g. AppVeyor).
PINNED = f"https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/{ASSET}"


def latest_url() -> str:
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    data = requests.get(API, headers=headers, timeout=60).json()
    if not isinstance(data, dict) or "assets" not in data:
        raise RuntimeError(f"unexpected API response: {str(data)[:150]}")
    return next(a["browser_download_url"] for a in data["assets"] if a["name"] == ASSET)


def main() -> None:
    os.makedirs(DEST, exist_ok=True)
    try:
        url = latest_url()
    except Exception as e:
        print(f"API lookup failed ({e}); using pinned release")
        url = PINNED
    print(f"downloading {url.rsplit('/', 1)[-1]}")
    data = requests.get(url, timeout=600).content
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(DEST)
    print("extracted into", DEST)
    for root, _, files in os.walk(DEST):
        for f in files:
            if f.endswith(".exe"):
                print("  exe:", os.path.relpath(os.path.join(root, f), DEST))


if __name__ == "__main__":
    main()
