# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Kaiwa** — a local-first Japanese conversation tutor (a Pingo AI clone) designed to run well even on modest, CPU-only hardware.
Runs offline by default: Ollama for the LLM, whisper.cpp for STT, VOICEVOX/macOS `say` for TTS, JMdict for dictionary lookups. Optional cloud LLM providers (Gemini/OpenAI/Anthropic) via user API keys — everything else stays local.

## Commands

```bash
./run.sh                      # start everything (ollama, VOICEVOX, uvicorn) → http://localhost:8130

# dev server only (assumes ollama already running):
.venv/bin/python -m uvicorn server.main:app --port 8130 --reload

# quick smoke tests (no test suite; endpoints are tested with curl):
curl -s localhost:8130/api/health                        # all subsystems status
.venv/bin/python -c "from server import jp; print(jp.annotate('食べました'))"   # furigana
.venv/bin/python -c "from server import dictionary; print(dictionary.lookup('大盛り'))"
```

Always use `.venv/bin/python` — the repo path contains a space, so quote it in shell commands.

## Architecture

FastAPI backend (`server/`) + single-page vanilla-JS frontend (`web/`, served at `/static`). SQLite persistence (`data/kaiwa.db`, schema in `db.py`, auto-created). No build step, no JS framework.

External processes the app talks to (start order matters, `run.sh` handles it):
- **Ollama** on `:11434` — model resolved at runtime by `llm.resolve_model()` from a preference list (default `qwen3:4b-instruct-2507-q4_K_M`). On CPU-only machines keep models ≤4B for usable latency (~10 tok/s); `setup.hardware_info()` recommends a tier from detected RAM/arch.
- LLM access always goes through `llm.py`'s provider abstraction: `chat_stream()`/`chat_json()` take a cfg dict from `main.llm_config()` (provider `ollama`/`gemini`/`openai`/`anthropic`, raw-HTTP, no SDKs). API keys live in settings but are stripped from every response by `main._safe_profile()` — keep it that way.
- `setup.py` = first-run hardware detection, Ollama model recommendation, Tailscale status for the phone guide. `backup.py` = SQLite-snapshot backups (export/import + hourly scheduler thread for daily/weekly auto-backup).
- **VOICEVOX engine** on `:50021` — optional, binary at `vendor/macos-x64/run` (~20s boot). `tts.py` auto-falls-back to macOS `say -v Kyoko` when it's down. Voice ids: `vv:<style_id>` / `aivis:<style_id>` / `say:<Name>`. `tts.ENGINES` is a registry of VOICEVOX-protocol engines — AivisSpeech on `:10101` (emotional/anime-style voices, user-installed, auto-detected) rides the same code path. Synthesis takes an `intonation` param (VOICEVOX `intonationScale`, "Expressiveness" in settings).
- **whisper-cli** (brew) + `models/ggml-small.bin` — `stt.py` expects 16kHz mono WAV; the browser records WAV directly (`encodeWav` in `app.js`), so no ffmpeg anywhere.

Chat request flow (the core path): `POST /api/chat` (main.py) → system prompt built per-turn by `prompts.tutor_system_prompt()` from profile + mode/scenario + recent mistakes/vocab from db ("memory") → `llm.chat_stream()` → SSE deltas to browser → on completion the reply is annotated (`jp.annotate()` furigana ruby alignment, `jp.romaji()`) and sent as a final SSE event. Grammar corrections are **not** in this path — the frontend fires `POST /api/correct` asynchronously per user message so chat latency stays low; confirmed errors land in `mistakes` and feed back into future system prompts.

Voice Call mode (mode `call`) reuses the same `/api/chat` stream, but entirely client-side in `app.js` (the `call` object): deltas are split at sentence boundaries (`。！？!?\n`) and each sentence is fetched from `GET /api/tts` and played while the rest still streams; when playback + stream finish, the mic opens automatically with RMS-energy VAD (~1.2s silence ends the utterance) → `/api/stt` → next turn. Half-duplex; tapping the avatar interrupts playback (the SSE stream is still read to completion so the reply is saved). The `call` prompt branch in `prompts.py` forbids emoji/markdown because everything it writes is spoken by TTS.

Word lookups (`POST /api/word`): JMdict SQLite first (exact form, then `jp.lemma_of()` dictionary form) — instant and accurate; LLM fallback only when JMdict misses. `dictionary.build_if_needed()` builds `data/jmdict.db` from `models/jmdict-eng-*.json` on first use. Never let the 4B model answer dictionary-style questions when JMdict can — it confabulates meanings.

All other LLM analysis tasks (corrections, hints, translation, session summaries) go through `llm.chat_json()` which uses Ollama JSON mode; prompts live in `prompts.py` and must demand strict JSON. The 4B model drifts into Japanese for meta-text — prompts explicitly require English where it matters.

Scenario/lesson catalog is code, not DB: `scenarios.py` (36 roleplay scenarios, 10 guided lessons). SRS is SM-2 in `db.srs_review()` (grades 0-3).

## Phone / PWA

The server binds `0.0.0.0:8130`; `run.sh` auto-runs `tailscale serve` (if Tailscale is installed and signed in) to expose an HTTPS URL — required because phone browsers block `getUserMedia` (mic) on plain HTTP. `web/manifest.json` + `icon-*.png` make it installable via Add to Home Screen; on ≤760px the sidebar becomes a bottom tab bar.

UI icons are Lucide (ISC license), self-hosted as a single sprite at `web/icons.svg` (built from lucide-static SVGs; regenerate by re-running the sprite script if adding icons). Frontend uses `icon(name)` in `app.js`; scenario ids map to icons in `ICON_MAP` there — new scenarios in `scenarios.py` need a matching `ICON_MAP` entry or they fall back to `message-circle`.

## Conventions

- `jp.py` tokenizer backend is fugashi (UniDic) with janome fallback; furigana works by regex-aligning kana runs in the surface against the reading (`_ruby_segments`) — test with mixed kanji/okurigana words like 美味しい, 食べる.
- User-visible strings on the frontend are English; tutor content is Japanese.
- TTS output is cached in `data/tts_cache/` keyed by (voice, speed, text) hash.
- Reset app state: delete `data/kaiwa.db` (recreated empty; triggers onboarding again).
