<div align="center">

<img src="docs/cover.jpg" alt="Kaiwa! 会話 — Your Private Japanese Conversation Tutor" width="100%">

**Your private Japanese tutor — chat, voice calls, roleplay, corrections, and spaced repetition, running entirely on your own computer.**

[![Release](https://img.shields.io/github/v/release/kroogies/Kaiwa)](https://github.com/kroogies/Kaiwa/releases/latest)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20(beta)-lightgrey)
![Local first](https://img.shields.io/badge/AI-100%25%20local%20by%20default-success)

</div>

No subscriptions. No account. Your conversations never leave your machine
(unless *you* plug in a cloud AI key — see [Choose your AI](#choose-your-ai)).

## Get it

Grab the zip for your OS from the **[latest release](https://github.com/kroogies/Kaiwa/releases/latest)**, unzip, and run:

**macOS**
```bash
./setup.sh    # venv + dependencies + speech model + dictionary (~600 MB)
./run.sh      # starts everything → http://localhost:8130
```
Voice input additionally needs whisper.cpp: `brew install whisper-cpp`

**Windows (beta)** — in PowerShell:
```powershell
.\setup.ps1
.\run.ps1     # → http://localhost:8130
```

Both need [Ollama](https://ollama.com) installed (the free local AI that powers
Kaiwa by default). First launch opens an onboarding wizard that checks your
hardware, recommends a model that will actually be responsive on it, and takes
~30s to warm up.

> Developing or contributing? `git clone` this repo instead — `main` is the
> stable release, `dev` is where work happens.

## What it does

| Feature | How |
|---|---|
| 💬 **Free Chat** | Natural conversation with Kaiwa, your AI tutor, at your JLPT level (N5–N1) |
| 📞 **Voice Call** | Real-time spoken conversation — just talk, no typing |
| 🎬 **36 roleplay scenarios** | Ramen shop, job interview, izakaya, kōban, ryokan… |
| 🎭 **Custom roleplay** | Define any scene, any roles |
| 📖 **10 guided lessons** | Structured mini-lessons (greetings → keigo) |
| ✏️ **Live corrections** | Every message checked; mistakes explained in English & remembered — and correctly-used advanced kanji gets praised, not "corrected" |
| 💡 **Hints** | Stuck? Get 3 suggested replies at your level |
| ふ **Furigana / romaji / translation** | Toggle per conversation, tap any word for its meaning |
| 📚 **Dictionary** | JMdict (490k+ entries) — tap words in chat, or search Japanese/English in the Dictionary tab. Fully offline |
| 🃏 **SRS review** | Anki-style spaced repetition — grade buttons show exactly when each word comes back |
| 📝 **Session reports** | Summary, strengths, focus areas — expandable in Progress, savable as PDF |
| 📈 **Progress** | Streaks, minutes practiced, mistake patterns |
| 🧠 **Memory** | Your recent mistakes & words feed back into the tutor's brain |
| 💾 **Backups** | Automatic daily/weekly backups + one-click export/import — moves cleanly between macOS and Windows |

## Choose your AI

Kaiwa works with either:

- **Local AI (default)** — [Ollama](https://ollama.com) running a small model on
  your computer. Free, 100% private, works offline. The first-run wizard checks
  your hardware and recommends a model that will actually be responsive on it.
  Realistic minimum: ~8 GB RAM; a CPU-only machine runs a 4B model at
  conversational (not instant) speed.
- **Cloud AI (optional)** — paste an API key for **Google Gemini** (has a free
  tier), **OpenAI**, or **Anthropic Claude** in Settings. Much faster and
  smarter; your messages go to that provider. Keys are stored only in your
  local database and are never shown to the browser again.

Speech recognition, speech synthesis, the dictionary, and all your data stay
local either way.

### Better voices (optional)

Out of the box Kaiwa speaks with your OS's built-in Japanese voice (Kyoko on
macOS, Haruka on Windows — on Windows you may need to add **日本語** under
Settings → Time & Language → Language with the Speech option). For much nicer
voices, download the [VOICEVOX engine](https://github.com/VOICEVOX/voicevox_engine/releases)
(CPU build for your OS) and unzip it into `vendor/` so that the launcher file exists:

- macOS: `vendor/macos-x64/run`
- Windows: `vendor\windows-cpu\run.exe`

The launcher picks it up automatically, and a voice picker (with preview)
appears in Settings. Every VOICEVOX character × emotion style (sweet, tsundere,
whisper…) shows up there, and the **Expressiveness** slider in Settings makes
any of them swing harder.

### Anime-style voices (optional)

For the most natural, emotional voices, install [AivisSpeech](https://aivis-project.com/)
(free, Windows/macOS) and add character voice models from
[AivisHub](https://hub.aivis-project.com/) inside the app — 60+ free
anime-style voices. Its engine speaks the VOICEVOX API, so Kaiwa detects it
automatically (`run.sh` even starts it for you if installed) and its voices
appear in the same Settings picker. Heads-up: it's a heavier model than
VOICEVOX — on older CPU-only machines each sentence takes a few seconds to
synthesize (cached after the first time). Headless alternative: unzip
[AivisSpeech-Engine](https://github.com/Aivis-Project/AivisSpeech-Engine/releases)
into `vendor/aivisspeech-engine/`.

## Use it on your phone 📱

Your computer does all the AI work; the phone is just a screen. The free
[Tailscale](https://tailscale.com) app connects them securely from anywhere:

1. Install Tailscale on this computer and sign in
2. Install Tailscale on your phone, sign in with the **same account**
3. Restart Kaiwa (`./run.sh`), open **Settings → On your phone**, and scan the QR code
4. On the phone: Share → **Add to Home Screen** → Kaiwa installs like a real app

Why not plain Wi-Fi? Phone browsers block the microphone on insecure HTTP —
Tailscale provides the HTTPS link that makes voice work.

## Your data

Everything lives in one file: `data/kaiwa.db`. In **Settings → Your data** you
can export it, import it on a new machine (macOS ↔ Windows both ways), turn on
automatic daily/weekly backups (kept in `~/Documents/Kaiwa Backups`, last 8
rotated), or reset everything for a fresh start. Tip: point your backups at a
folder inside iCloud Drive/Dropbox and they sync off-machine too.

## Configuration

| Env var | Default | What |
|---|---|---|
| `KAIWA_PORT` | `8130` | Web app port |
| `KAIWA_OLLAMA_URL` | `http://localhost:11434` | Ollama server |

Logs land in `/tmp/ollama.log` and `/tmp/voicevox.log`.

## The stack

FastAPI + SQLite + vanilla JS (no build step). STT: whisper.cpp. TTS: VOICEVOX,
AivisSpeech, macOS `say`, or Windows SAPI. Tokenizer/furigana: fugashi (UniDic).
LLM: Ollama or Gemini/OpenAI/Anthropic over plain HTTP.

## Contributing

Issues and PRs welcome — branch off `dev`. If Kaiwa helps your Japanese, a ⭐
helps other learners find it.

## Credits & data licenses

- Dictionary data from [JMdict](https://www.edrdg.org/jmdict/j_jmdict.html)
  (via [jmdict-simplified](https://github.com/scriptin/jmdict-simplified)),
  property of the [EDRDG](https://www.edrdg.org/), used under
  [CC BY-SA 4.0](https://www.edrdg.org/edrdg/licence.html)
- [VOICEVOX](https://voicevox.hiroshiba.jp/) — generated audio must be credited
  per each voice library's terms (e.g. `VOICEVOX:四国めたん`)
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (MIT),
  [Ollama](https://ollama.com) (MIT)
- Icons: [Lucide](https://lucide.dev) (ISC) ·
  QR: [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) (MIT)

## License

[AGPL-3.0](LICENSE) — free to use, modify, and share; if you run a modified
version as a service, you must share your changes.
