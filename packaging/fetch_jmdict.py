"""Download the latest JMdict (English) source into models/ for bundling.

The .json is git-ignored (112 MB), so CI fetches it before the PyInstaller build.
dictionary.py builds jmdict.db from it at runtime (in the writable data dir).
"""
import io
import os
import zipfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "models")
API = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
# Fallback when the API is unauthenticated + rate-limited (e.g. AppVeyor). Kept
# current-ish; the API path picks up newer releases automatically when it works.
PINNED = ("https://github.com/scriptin/jmdict-simplified/releases/download/"
          "3.6.2%2B20260713141310/jmdict-eng-3.6.2%2B20260713141310.json.zip")


def latest_url() -> str:
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):  # avoids unauthenticated API rate limits
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    data = requests.get(API, headers=headers, timeout=60).json()
    if not isinstance(data, dict) or "assets" not in data:
        raise RuntimeError(f"unexpected API response: {str(data)[:150]}")
    return next(a["browser_download_url"] for a in data["assets"]
                if a["name"].startswith("jmdict-eng-")
                and "common" not in a["name"]
                and a["name"].endswith(".json.zip"))


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
    print("extracted:", [f for f in os.listdir(DEST) if f.endswith(".json")])


if __name__ == "__main__":
    main()
