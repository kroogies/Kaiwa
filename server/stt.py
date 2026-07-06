"""Speech-to-text via whisper.cpp (whisper-cli). Expects 16kHz mono WAV input."""
import os
import re
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "models", "ggml-small.bin")


def available() -> bool:
    return shutil.which("whisper-cli") is not None and os.path.exists(MODEL)


def transcribe(wav_bytes: bytes, language: str = "ja") -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        path = f.name
    try:
        proc = subprocess.run(
            ["whisper-cli", "-m", MODEL, "-f", path, "-l", language,
             "-t", "6", "-nt", "--no-prints"],
            capture_output=True, text=True, timeout=120,
        )
        text = proc.stdout.strip()
        # strip bracketed non-speech artifacts like [音楽], (笑い)
        text = re.sub(r"[\[(（【][^\])）】]*[\])）】]", "", text).strip()
        return text
    finally:
        os.unlink(path)
