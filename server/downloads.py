"""Streaming file downloads with progress — used by first-run setup.

Kept deliberately tiny: the only consumer is the onboarding wizard downloading
the whisper STT model, streamed to the browser as SSE progress.
"""
import os

import requests


def download(url: str, dest: str, chunk: int = 1 << 20):
    """Download ``url`` to ``dest``, yielding (downloaded_bytes, total_bytes).

    Streams to a ``.part`` file and renames on success so an interrupted
    download never looks complete. ``total`` is 0 if the server omits
    Content-Length.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            for block in r.iter_content(chunk_size=chunk):
                if not block:
                    continue
                f.write(block)
                done += len(block)
                yield done, total
    os.replace(tmp, dest)
