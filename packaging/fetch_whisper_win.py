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


def main() -> None:
    os.makedirs(DEST, exist_ok=True)
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    rel = requests.get(API, headers=headers, timeout=60).json()
    asset = next(a for a in rel["assets"] if a["name"] == ASSET)
    print(f"downloading {asset['name']} ({asset['size'] // 1048576} MB)")
    data = requests.get(asset["browser_download_url"], timeout=600).content
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(DEST)
    print("extracted into", DEST)
    for root, _, files in os.walk(DEST):
        for f in files:
            if f.endswith(".exe"):
                print("  exe:", os.path.relpath(os.path.join(root, f), DEST))


if __name__ == "__main__":
    main()
