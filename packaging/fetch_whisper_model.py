"""Download the whisper STT model into models/ for bundling.

The weights are git-ignored (~465 MB), so CI fetches them before the PyInstaller
build. Bundled so speech-to-text works out of the box with no first-run download.
"""
import os

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "models", "ggml-small.bin")
URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"


def main() -> None:
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    if os.path.exists(DEST) and os.path.getsize(DEST) > 400 * 1024 * 1024:
        print("model already present, skipping")
        return
    tmp = DEST + ".part"
    with requests.get(URL, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            for block in r.iter_content(chunk_size=1 << 20):
                f.write(block)
                done += len(block)
        print(f"downloaded {done // 1048576} MB (expected {total // 1048576} MB)")
    os.replace(tmp, DEST)


if __name__ == "__main__":
    main()
