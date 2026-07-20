"""Stage a trimmed VOICEVOX TTS engine (engine + a few default voices) for bundling.

The full engine is ~2 GB, almost all of it voice models (26 .vvm files). Kaiwa
ships the engine plus the handful of voices its default set uses and drops the
rest — VOICEVOX loads whatever .vvm files are present, so a subset simply exposes
fewer voices (verified: the engine boots and synthesizes fine).

Usage: python packaging/stage_voicevox.py [dest] [src]
  dest defaults to vendor/voicevox, src to vendor/macos-x64 (the repo's engine).
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 四国めたん・ずんだもん・春日部つむぎ・雨晴はう (0) · 冥鳴ひまり (1) · 九州そら (2)
# · 青山龍星・もち子さん・小夜 (15) — covers Kaiwa's PREFERRED_VV_STYLES.
KEEP = {"0.vvm", "1.vvm", "2.vvm", "15.vvm"}


def stage(src: str, dest: str) -> None:
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("model"))
    os.makedirs(os.path.join(dest, "model"), exist_ok=True)
    src_model = os.path.join(src, "model")
    for f in os.listdir(src_model):
        if f in KEEP or not f.endswith(".vvm"):  # keep support files, drop unused voices
            shutil.copy2(os.path.join(src_model, f), os.path.join(dest, "model", f))
    if sys.platform == "darwin":  # ad-hoc re-sign so a de-quarantined copy runs
        for root, _, files in os.walk(dest):
            for name in files:
                if name == "run" or name.endswith((".dylib", ".so")):
                    subprocess.run(["codesign", "--force", "--sign", "-",
                                    os.path.join(root, name)], capture_output=True)


def main() -> None:
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "vendor", "voicevox")
    src = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "vendor", "macos-x64")
    if not os.path.isdir(src):
        print(f"source engine not found: {src} — skipping VOICEVOX bundling")
        return
    stage(src, dest)
    size = subprocess.run(["du", "-sh", dest], capture_output=True, text=True).stdout.split()[0] \
        if os.name != "nt" else "?"
    print(f"staged trimmed VOICEVOX into {dest} ({size}); "
          f"voices: {sorted(f for f in os.listdir(os.path.join(dest, 'model')) if f.endswith('.vvm'))}")


if __name__ == "__main__":
    main()
