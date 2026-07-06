"""Text-to-speech: VOICEVOX engine (if running on :50021) with macOS `say` fallback.

Voice ids: "vv:<style_id>" for VOICEVOX, "say:<VoiceName>" for macOS voices.
Returns WAV bytes. Results cached on disk by (text, voice, speed).
"""
import hashlib
import os
import re
import subprocess
import tempfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "tts_cache")
VOICEVOX = "http://localhost:50021"
PREFERRED_VV_STYLES = [8, 2, 3, 13, 14]  # 春日部つむぎ, 四国めたん, ずんだもん, 青山龍星, 冥鳴ひまり


def voicevox_up() -> bool:
    try:
        requests.get(f"{VOICEVOX}/version", timeout=2)
        return True
    except Exception:
        return False


def _clean(text: str) -> str:
    """Strip markdown/emoji-ish noise that TTS engines stumble on."""
    text = re.sub(r"[*_#`~>|]", "", text)
    text = re.sub(r"[😀-🿿🀀-🯿☀-➿✀-➿]", "", text)
    return text.strip()


def list_voices() -> list:
    voices = []
    if voicevox_up():
        try:
            for sp in requests.get(f"{VOICEVOX}/speakers", timeout=5).json():
                for st in sp["styles"]:
                    voices.append({
                        "id": f"vv:{st['id']}",
                        "label": f"{sp['name']}({st['name']})",
                        "engine": "VOICEVOX",
                    })
        except Exception:
            pass
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if "ja_JP" in line:
                name = line.split()[0]
                voices.append({"id": f"say:{name}", "label": name, "engine": "macOS"})
    except Exception:
        pass
    return voices


def default_voice() -> str:
    if voicevox_up():
        try:
            styles = {st["id"] for sp in requests.get(f"{VOICEVOX}/speakers", timeout=5).json()
                      for st in sp["styles"]}
            for pref in PREFERRED_VV_STYLES:
                if pref in styles:
                    return f"vv:{pref}"
            if styles:
                return f"vv:{sorted(styles)[0]}"
        except Exception:
            pass
    return "say:Kyoko"


def synthesize(text: str, voice: str, speed: float = 1.0) -> bytes:
    text = _clean(text)
    if not text:
        return b""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(f"{voice}|{speed}|{text}".encode()).hexdigest()
    cached = os.path.join(CACHE, key + ".wav")
    if os.path.exists(cached):
        with open(cached, "rb") as f:
            return f.read()

    if voice.startswith("vv:") and voicevox_up():
        wav = _voicevox(text, int(voice[3:]), speed)
    else:
        name = voice[4:] if voice.startswith("say:") else "Kyoko"
        wav = _say(text, name, speed)

    if wav:
        with open(cached, "wb") as f:
            f.write(wav)
    return wav


def _voicevox(text: str, style_id: int, speed: float) -> bytes:
    q = requests.post(f"{VOICEVOX}/audio_query",
                      params={"text": text, "speaker": style_id}, timeout=30).json()
    q["speedScale"] = speed
    r = requests.post(f"{VOICEVOX}/synthesis",
                      params={"speaker": style_id}, json=q, timeout=120)
    r.raise_for_status()
    return r.content


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
