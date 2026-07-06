#!/bin/bash
# Kaiwa launcher — starts Ollama, VOICEVOX (if installed), and the app server.
set -e
cd "$(dirname "$0")"

echo "🗣️  Kaiwa — local Japanese tutor"
PORT="${KAIWA_PORT:-8130}"

# first run without setup? be helpful
[ -d .venv ] || { echo "✗ run ./setup.sh first"; exit 1; }

# 1. Ollama
if ! curl -s --max-time 2 http://localhost:11434/api/version >/dev/null; then
  echo "▶ starting ollama…"
  (ollama serve >/tmp/ollama.log 2>&1 &)
  for i in $(seq 1 20); do
    curl -s --max-time 1 http://localhost:11434/api/version >/dev/null && break
    sleep 1
  done
fi
echo "✓ ollama running"

# 2. VOICEVOX (optional, better voices)
if [ -x "vendor/macos-x64/run" ]; then
  if ! curl -s --max-time 2 http://127.0.0.1:50021/version >/dev/null; then
    echo "▶ starting VOICEVOX engine (takes ~20s)…"
    (cd vendor/macos-x64 && ./run --host 127.0.0.1 --port 50021 >/tmp/voicevox.log 2>&1 &)
  fi
fi

# 3. Tailscale HTTPS link (optional — lets your phone reach Kaiwa from anywhere)
TS="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
if [ -x "$TS" ] && "$TS" status >/dev/null 2>&1; then
  "$TS" serve --bg "$PORT" >/dev/null 2>&1 || true
  TSHOST=$("$TS" status --json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))" 2>/dev/null)
  [ -n "$TSHOST" ] && echo "📱 phone link: https://$TSHOST"
fi

# 4. App server (0.0.0.0 so phones on the network can connect)
echo "▶ starting Kaiwa at http://localhost:$PORT"
(sleep 2 && open "http://localhost:$PORT") &
exec .venv/bin/python -m uvicorn server.main:app --host 0.0.0.0 --port "$PORT"
