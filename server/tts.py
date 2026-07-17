"""Text-to-speech: VOICEVOX-protocol engines (if running) with an OS voice fallback.

Any engine speaking the VOICEVOX HTTP API works — VOICEVOX itself on :50021
and AivisSpeech (emotional, anime-style voices from AivisHub) on :10101.
Voice ids: "vv:<style_id>", "aivis:<style_id>" · "say:<Name>" macOS · "sapi:<Name>" Windows.
Returns WAV bytes. Results cached on disk by (text, voice, speed, intonation).
"""
import hashlib
import os
import platform
import re
import subprocess
import tempfile

import requests

from . import paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(paths.DATA_DIR, "tts_cache")
ENGINES = {
    # prefix: (label, base_url) — anything VOICEVOX-API-compatible slots in here
    "vv": ("VOICEVOX", "http://localhost:50021"),
    "aivis": ("AivisSpeech", "http://localhost:10101"),
}
PREFERRED_VV_STYLES = [8, 2, 3, 13, 14]  # 春日部つむぎ, 四国めたん, ずんだもん, 青山龍星, 冥鳴ひまり
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


def engine_up(prefix: str) -> bool:
    try:
        requests.get(f"{ENGINES[prefix][1]}/version", timeout=2)
        return True
    except Exception:
        return False


def voicevox_up() -> bool:
    return engine_up("vv")


def _clean(text: str) -> str:
    """Strip markdown/emoji-ish noise that TTS engines stumble on."""
    text = re.sub(r"[*_#`~>|]", "", text)
    text = re.sub(r"[😀-🿿🀀-🯿☀-➿✀-➿]", "", text)
    return text.strip()


def list_voices() -> list:
    voices = []
    for prefix, (label, base) in ENGINES.items():
        if not engine_up(prefix):
            continue
        try:
            for sp in requests.get(f"{base}/speakers", timeout=5).json():
                for st in sp["styles"]:
                    voices.append({
                        "id": f"{prefix}:{st['id']}",
                        "label": f"{sp['name']}({st['name']})",
                        "engine": label,
                    })
        except Exception:
            pass
    if IS_MAC:
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                if "ja_JP" in line:
                    name = line.split()[0]
                    voices.append({"id": f"say:{name}", "label": name, "engine": "macOS"})
        except Exception:
            pass
    elif IS_WINDOWS:
        ja, other = [], []
        for name, culture in _sapi_voices():
            entry = {"id": f"sapi:{name}", "label": name, "engine": "Windows"}
            (ja if culture.lower().startswith("ja") else other).append(entry)
        voices += ja or other  # only fall back to non-Japanese voices if there are none
    return voices


def _sapi_voices() -> list:
    """[(name, culture)] of installed Windows SAPI voices."""
    script = ("Add-Type -AssemblyName System.Speech; "
              "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | "
              "ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, timeout=15,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return [tuple(line.split("|", 1)) for line in out.splitlines() if "|" in line]
    except Exception:
        return []


def default_voice() -> str:
    for prefix, (_, base) in ENGINES.items():
        if not engine_up(prefix):
            continue
        try:
            styles = {st["id"] for sp in requests.get(f"{base}/speakers", timeout=5).json()
                      for st in sp["styles"]}
            if prefix == "vv":
                for pref in PREFERRED_VV_STYLES:
                    if pref in styles:
                        return f"vv:{pref}"
            if styles:
                return f"{prefix}:{sorted(styles)[0]}"
        except Exception:
            pass
    if IS_WINDOWS:
        voices = _sapi_voices()
        ja = [n for n, c in voices if c.lower().startswith("ja")]
        name = ja[0] if ja else (voices[0][0] if voices else "")
        return f"sapi:{name}"
    return "say:Kyoko"


def synthesize(text: str, voice: str, speed: float = 1.0, intonation: float = 1.0) -> bytes:
    text = _clean(text)
    if not text:
        return b""
    os.makedirs(CACHE, exist_ok=True)
    # default intonation keeps the pre-slider cache key, so old cache stays valid
    key_src = f"{voice}|{speed}|{text}" if intonation == 1.0 else f"{voice}|{speed}|{intonation}|{text}"
    key = hashlib.sha1(key_src.encode()).hexdigest()
    cached = os.path.join(CACHE, key + ".wav")
    if os.path.exists(cached):
        with open(cached, "rb") as f:
            return f.read()

    prefix = voice.split(":", 1)[0]
    if prefix in ENGINES and engine_up(prefix):
        wav = _vv_engine(ENGINES[prefix][1], text, int(voice.split(":", 1)[1]), speed, intonation)
    elif IS_WINDOWS:
        name = voice[5:] if voice.startswith("sapi:") else ""
        wav = _sapi(text, name, speed)
    else:
        name = voice[4:] if voice.startswith("say:") else "Kyoko"
        wav = _say(text, name, speed)

    if wav:
        with open(cached, "wb") as f:
            f.write(wav)
    return wav


def _vv_engine(base: str, text: str, style_id: int, speed: float, intonation: float) -> bytes:
    q = requests.post(f"{base}/audio_query",
                      params={"text": text, "speaker": style_id}, timeout=30).json()
    q["speedScale"] = speed
    q["intonationScale"] = intonation  # VOICEVOX: pitch swing; Aivis: emotion strength
    r = requests.post(f"{base}/synthesis",
                      params={"speaker": style_id}, json=q, timeout=120)
    r.raise_for_status()
    return r.content


def _sapi(text: str, name: str, speed: float) -> bytes:
    """Windows built-in voices via System.Speech (writes PCM WAV directly)."""
    rate = max(-10, min(10, round((speed - 1.0) * 10)))  # SAPI rate is -10..10
    with tempfile.TemporaryDirectory() as d:
        txt = os.path.join(d, "t.txt")
        wav = os.path.join(d, "t.wav")
        with open(txt, "w", encoding="utf-8") as f:
            f.write(text)  # via file — avoids all shell-quoting issues with Japanese text
        select = f"try {{ $s.SelectVoice('{name.replace(chr(39), chr(39) * 2)}') }} catch {{ }}; " if name else ""
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"{select}"
            f"$s.Rate = {rate}; "
            f"$s.SetOutputToWaveFile('{wav}'); "
            f"$t = Get-Content -Raw -Encoding UTF8 '{txt}'; "
            "$s.Speak($t); $s.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       check=True, timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with open(wav, "rb") as f:
            return f.read()


def _say(text: str, name: str, speed: float) -> bytes:
    rate = int(180 * speed)  # words-per-minute-ish; 180 ≈ natural for ja
    with tempfile.TemporaryDirectory() as d:
        aiff = os.path.join(d, "t.aiff")
        wav = os.path.join(d, "t.wav")
        subprocess.run(["say", "-v", name, "-r", str(rate), "-o", aiff, text],
                       check=True, timeout=60)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff, wav],
                       check=True, timeout=60)
        with open(wav, "rb") as f:
            return f.read()
