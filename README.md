# Kaiwa 会話 — your private Japanese tutor

A Japanese conversation tutor that runs **on your own computer**. Chat, hop on
voice calls, roleplay everyday scenarios, get corrected, save words, and review
them with spaced repetition — free, private, and offline-first.

No subscriptions. Your conversations never leave your machine (unless *you*
plug in a cloud AI key — see below).

> **Platforms:** macOS, and Windows (beta — feedback welcome!).

## What it does

| Feature | How |
|---|---|
| 💬 **Free Chat** | Natural conversation with Kaiwa, your AI tutor, at your JLPT level (N5–N1) |
| 📞 **Voice Call** | Real-time spoken conversation — just talk, no typing |
| 🎬 **36 roleplay scenarios** | Ramen shop, job interview, izakaya, kōban, ryokan… |
| 🎭 **Custom roleplay** | Define any scene, any roles |
| 📖 **10 guided lessons** | Structured mini-lessons (greetings → keigo) |
| ✏️ **Live corrections** | Every message checked; mistakes explained in English & remembered |
| 💡 **Hints** | Stuck? Get 3 suggested replies at your level |
| ふ **Furigana / romaji / translation** | Toggle per conversation, tap any word for its meaning |
| 📚 **Dictionary** | JMdict (490k+ entries) — tap words in chat, or search Japanese/English in the Dictionary tab. Fully offline |
| 🃏 **SRS review** | Anki-style spaced repetition for words you save |
| 📝 **Session reports** | Summary, strengths, focus areas — expandable in Progress, savable as PDF |
| 📈 **Progress** | Streaks, minutes practiced, mistake patterns |
| 🧠 **Memory** | Your recent mistakes & words feed back into the tutor's brain |
| 💾 **Backups** | Automatic daily/weekly backups + one-click export/import to move machines |

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

## Install (macOS)

```bash
git clone <this repo>
cd kaiwa
./setup.sh    # venv + dependencies + speech model + dictionary (~600 MB)
./run.sh      # starts everything → http://localhost:8130
```

First launch opens an onboarding wizard that sets up your AI (local or cloud)
and takes ~30s to warm up. Voice input additionally needs whisper.cpp:

```bash
brew install whisper-cpp
```

## Install (Windows — beta)

1. Install [Python 3.11+](https://www.python.org/downloads/) — tick **"Add python.exe to PATH"**
2. Install [Ollama for Windows](https://ollama.com/download/windows) (skip if you'll use a cloud API key)
3. Clone this repo, then in the folder:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1   # deps + speech model + dictionary + whisper.cpp
powershell -ExecutionPolicy Bypass -File run.ps1     # starts everything → http://localhost:8130
```

For spoken replies without VOICEVOX, add a Japanese voice to Windows:
Settings → Time & Language → Language → add **日本語** with the Speech option.

### Better voices (optional)

Out of the box Kaiwa speaks with your OS's built-in Japanese voice (Kyoko on
macOS, Haruka on Windows). For much nicer voices, download the
[VOICEVOX engine](https://github.com/VOICEVOX/voicevox_engine/releases)
CPU build for your platform and unzip it so that this file exists:

- macOS: `vendor/macos-x64/run`
- Windows: `vendor\windows-cpu\run.exe`

The launcher picks it up automatically, and a voice picker (with preview)
appears in Settings.

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
can export it, import it on a new machine, and turn on automatic daily/weekly
backups (kept in `~/Documents/Kaiwa Backups`, last 8 rotated). Tip: point your
backups at a folder inside iCloud Drive/Dropbox and they sync off-machine too.

Reset everything: delete `data/kaiwa.db`.

## Configuration

| Env var | Default | What |
|---|---|---|
| `KAIWA_PORT` | `8130` | Web app port |
| `KAIWA_OLLAMA_URL` | `http://localhost:11434` | Ollama server |

Logs land in `/tmp/ollama.log` and `/tmp/voicevox.log`.

## The stack

FastAPI + SQLite + vanilla JS (no build step). STT: whisper.cpp. TTS: VOICEVOX
or macOS `say`. Tokenizer/furigana: fugashi (UniDic). LLM: Ollama or
Gemini/OpenAI/Anthropic over plain HTTP.

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
