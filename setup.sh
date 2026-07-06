#!/bin/bash
# Kaiwa one-time setup: Python env, dependencies, speech model, dictionary.
set -e
cd "$(dirname "$0")"

echo "🗣  Kaiwa setup"

command -v python3 >/dev/null || { echo "✗ python3 is required — https://www.python.org"; exit 1; }

if [ ! -d .venv ]; then
  echo "▶ creating Python environment…"
  python3 -m venv .venv
fi
echo "▶ installing dependencies…"
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

mkdir -p data models

# whisper.cpp speech-recognition model (~466 MB)
if [ ! -f models/ggml-small.bin ]; then
  echo "▶ downloading speech-recognition model (466 MB)…"
  curl -L --progress-bar -o models/ggml-small.bin \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
fi

# JMdict dictionary (latest jmdict-simplified English release)
if ! ls models/jmdict-eng-*.json >/dev/null 2>&1; then
  echo "▶ downloading JMdict dictionary…"
  JM_URL=$(curl -s https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest \
    | grep -o '"browser_download_url": *"[^"]*jmdict-eng-[0-9][^"]*\.json\.zip"' \
    | head -1 | cut -d'"' -f4)
  if [ -n "$JM_URL" ]; then
    curl -L --progress-bar -o /tmp/kaiwa-jmdict.zip "$JM_URL"
    unzip -oq /tmp/kaiwa-jmdict.zip -d models/
    rm -f /tmp/kaiwa-jmdict.zip
  else
    echo "⚠ couldn't reach the JMdict release — download a jmdict-eng-*.json from"
    echo "  https://github.com/scriptin/jmdict-simplified/releases and put it in models/"
  fi
fi

if ! command -v whisper-cli >/dev/null 2>&1; then
  echo "⚠ voice input needs whisper.cpp:  brew install whisper-cpp"
fi

echo "✓ setup complete — start Kaiwa with ./run.sh"
