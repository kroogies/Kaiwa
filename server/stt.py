"""Speech-to-text via whisper.cpp (whisper-cli). Expects 16kHz mono WAV input."""
import os
import re
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "models", "ggml-small.bin")
_EXE = ".exe" if os.name == "nt" else ""


def _bin() -> str | None:
    """whisper.cpp CLI: env override → PATH → binaries dropped in vendor/whisper/."""
    env = os.environ.get("KAIWA_WHISPER_BIN")
    if env and (os.path.exists(env) or shutil.which(env)):
        return env
    for name in ("whisper-cli", "whisper-cpp"):
        p = shutil.which(name)
        if p:
            return p
    for name in (f"whisper-cli{_EXE}", f"main{_EXE}"):
        for sub in ("", "Release"):  # windows release zips sometimes nest a Release/ dir
            cand = os.path.join(ROOT, "vendor", "whisper", sub, name)
            if os.path.exists(cand):
                return cand
    return None


def available() -> bool:
    return _bin() is not None and os.path.exists(MODEL)


def transcribe(wav_bytes: bytes, language: str = "ja") -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        path = f.name
    try:
        proc = subprocess.run(
            [_bin(), "-m", MODEL, "-f", path, "-l", language,
             "-t", "6", "-nt", "--no-prints"],
            capture_output=True, text=True, timeout=120,
        )
        text = proc.stdout.strip()
        # strip bracketed non-speech artifacts like [音楽], (笑い)
        text = re.sub(r"[\[(（【][^\])）】]*[\])）】]", "", text).strip()
        return text
    finally:
        os.unlink(path)
