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


def main() -> None:
    os.makedirs(DEST, exist_ok=True)
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):  # avoid unauthenticated API rate limits in CI
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    rel = requests.get(API, headers=headers, timeout=60).json()
    asset = next(a for a in rel["assets"]
                 if a["name"].startswith("jmdict-eng-")
                 and "common" not in a["name"]
                 and a["name"].endswith(".json.zip"))
    print(f"downloading {asset['name']} ({asset['size'] // 1048576} MB)")
    data = requests.get(asset["browser_download_url"], timeout=600).content
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(DEST)
    print("extracted:", [f for f in os.listdir(DEST) if f.endswith(".json")])


if __name__ == "__main__":
    main()
