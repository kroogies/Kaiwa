"""Speech-to-text via whisper.cpp (whisper-cli). Expects 16kHz mono WAV input."""
import os
import re
import shutil
import subprocess
import tempfile

from . import paths

MODEL_NAME = "ggml-small.bin"  # ~465 MB; good accuracy/latency for Japanese on CPU
_EXE = ".exe" if os.name == "nt" else ""


def _model() -> str | None:
    """Path to the whisper weights: bundled in the app, or a user-dropped copy."""
    for d in (paths.MODELS_DIR, paths.BUNDLED_MODELS_DIR):
        p = os.path.join(d, MODEL_NAME)
        if os.path.exists(p):
            return p
    return None


def _ensure_exec(path: str) -> None:
    """PyInstaller's data copy can drop the executable bit — put it back."""
    if os.name == "nt":
        return
    try:
        os.chmod(path, os.stat(path).st_mode | 0o111)
    except OSError:
        pass


def _bin() -> str | None:
    """whisper.cpp CLI: env override → PATH install → binary bundled in the app.

    A PATH install (e.g. Homebrew — reachable in the frozen app because paths.py
    puts Homebrew back on PATH) is preferred because it's self-consistent with
    its own ggml backend libraries. The bundled binary is the fallback for a
    plain install with no whisper.cpp on the system. (Mixing the two — e.g. the
    bundled binary loading a Homebrew machine's ggml backends — can pull in two
    copies of libomp and crash, so we never straddle the two.)
    """
    env = os.environ.get("KAIWA_WHISPER_BIN")
    if env and (os.path.exists(env) or shutil.which(env)):
        return env
    for name in ("whisper-cli", "whisper-cpp"):
        p = shutil.which(name)
        if p:
            return p
    for name in (f"whisper-cli{_EXE}", f"main{_EXE}"):
        for sub in ("", "Release"):  # windows release zips sometimes nest a Release/ dir
            cand = os.path.join(paths.VENDOR_DIR, "whisper", sub, name)
            if os.path.exists(cand):
                _ensure_exec(cand)
                return cand
    return None


def available() -> bool:
    return _bin() is not None and _model() is not None


def transcribe(wav_bytes: bytes, language: str = "ja") -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        path = f.name
    try:
        proc = subprocess.run(
            [_bin(), "-m", _model(), "-f", path, "-l", language,
             "-t", "6", "-nt", "--no-prints"],
            capture_output=True, text=True, timeout=120, env=paths.system_env(),
        )
        text = proc.stdout.strip()
        # strip bracketed non-speech artifacts like [音楽], (笑い)
        text = re.sub(r"[\[(（【][^\])）】]*[\])）】]", "", text).strip()
        return text
    finally:
        os.unlink(path)
