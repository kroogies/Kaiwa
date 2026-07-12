"""Kaiwa — local Japanese conversation tutor (Pingo-style), fully offline.

LLM: Ollama (Qwen3-4B) · STT: whisper.cpp · TTS: VOICEVOX / macOS say
"""
import io
import json
import os
from datetime import date

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import (FileResponse, JSONResponse, Response,
                               StreamingResponse)
from fastapi.staticfiles import StaticFiles

import requests

from starlette.background import BackgroundTask

from . import backup, db, dictionary, jp, llm, prompts, scenarios, setup, stt, tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

app = FastAPI(title="Kaiwa")
db.init()
backup.start_scheduler()


def setting(key, default=None):
    return db.get_setting(key, default)


def current_model() -> str | None:
    return llm.resolve_model(setting("model"))


def llm_config() -> dict:
    """Active provider config for llm.chat_stream / llm.chat_json."""
    provider = setting("provider", "ollama")
    if provider not in llm.PROVIDERS:
        provider = "ollama"
    if provider == "ollama":
        return {"provider": "ollama", "model": current_model(), "key": None}
    info = llm.PROVIDERS[provider]
    return {
        "provider": provider,
        "model": setting(f"model_{provider}") or info["models"][0],
        "key": (setting(f"api_key_{provider}") or "").strip(),
    }


# ------------------------------------------------------------------- static

@app.get("/")
def index():
    return FileResponse(os.path.join(WEB, "index.html"))


app.mount("/static", StaticFiles(directory=WEB), name="static")


# ------------------------------------------------------------------- health

@app.get("/api/health")
def health():
    cfg = llm_config()
    return {
        "provider": cfg["provider"],
        "provider_label": llm.PROVIDERS[cfg["provider"]]["label"],
        "llm_ready": llm.not_ready_reason(cfg) is None,
        "ollama": llm.ollama_up(),
        "model": cfg["model"],
        "models": llm.list_models(),
        "whisper": stt.available(),
        "voicevox": tts.voicevox_up(),
        "aivis": tts.engine_up("aivis"),
        "tokenizer": jp.backend_name(),
        "dictionary": dictionary.available(),
    }


@app.get("/api/setup/hardware")
def setup_hardware():
    return setup.hardware_info()


@app.get("/api/setup/phone")
def setup_phone():
    return setup.phone_info()


@app.post("/api/setup/pull")
async def setup_pull(req: Request):
    """SSE proxy of Ollama's model download so the wizard can show live progress."""
    body = await req.json()
    name = (body.get("model") or "").strip()
    if not name:
        return JSONResponse({"error": "no model given"}, status_code=400)

    def gen():
        try:
            with requests.post(f"{llm.OLLAMA}/api/pull", json={"model": name},
                               stream=True, timeout=None) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        yield f"data: {line.decode()}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/providers")
def providers():
    """Provider catalog for the Settings UI (never returns the keys themselves)."""
    s = db.get_profile()["settings"]
    return {
        "active": s.get("provider", "ollama"),
        "providers": [
            {
                "id": pid,
                "label": info["label"],
                "needs_key": info["needs_key"],
                "models": info["models"] if pid != "ollama" else llm.list_models(),
                "has_key": bool((s.get(f"api_key_{pid}") or "").strip()),
                "model": s.get(f"model_{pid}") if pid != "ollama" else s.get("model"),
            }
            for pid, info in llm.PROVIDERS.items()
        ],
    }


# ------------------------------------------------------------------ profile

def _safe_profile() -> dict:
    """Profile with API keys stripped — the UI only needs to know they exist (/api/providers)."""
    p = db.get_profile()
    p["settings"] = {k: v for k, v in p["settings"].items() if not k.startswith("api_key_")}
    return p


@app.get("/api/profile")
def get_profile():
    p = _safe_profile()
    s = p["settings"]
    s.setdefault("provider", "ollama")
    s.setdefault("voice", tts.default_voice())
    s.setdefault("speed", 1.0)
    s.setdefault("intonation", 1.0)
    s.setdefault("auto_play", True)
    s.setdefault("furigana", True)
    s.setdefault("romaji", False)
    s.setdefault("auto_translate", False)
    s.setdefault("model", current_model())
    return p


@app.put("/api/profile")
async def put_profile(req: Request):
    body = await req.json()
    db.update_profile(body)
    return _safe_profile()


@app.post("/api/settings")
async def post_settings(req: Request):
    db.set_settings(await req.json())
    return _safe_profile()["settings"]


@app.get("/api/voices")
def voices():
    return {"voices": tts.list_voices(), "default": tts.default_voice()}


# ---------------------------------------------------------------- scenarios

@app.get("/api/scenarios")
def get_scenarios():
    return scenarios.catalog()


# ----------------------------------------------------------------- sessions

@app.post("/api/sessions")
async def create_session(req: Request):
    body = await req.json()
    mode = body.get("mode", "free_chat")
    scen = None
    sid_key = None
    if mode in ("roleplay", "lesson"):
        if body.get("scenario_id"):
            scen = scenarios.get(body["scenario_id"])
            sid_key = body["scenario_id"]
        elif body.get("custom"):
            c = body["custom"]
            scen = {
                "id": "custom", "title": c.get("title", "Custom Roleplay"),
                "description": c.get("description", ""),
                "ai_role": c.get("ai_role", ""), "user_role": c.get("user_role", ""),
                "setting": c.get("setting", ""), "target_vocab": [], "kind": "roleplay",
            }
            sid_key = "custom"
    session_id = db.create_session(mode, sid_key, scen)
    return {"session_id": session_id, "scenario": scen}


@app.get("/api/sessions/{sid}/messages")
def session_messages(sid: int):
    msgs = db.get_messages(sid)
    for m in msgs:
        if m["role"] == "assistant":
            m["tokens"] = jp.annotate(m["text"])
            m["romaji"] = jp.romaji(m["text"])
    return {"messages": msgs}


def _history(sid: int, limit=16) -> list:
    msgs = db.get_messages(sid)
    return [{"role": m["role"], "content": m["text"]} for m in msgs[-limit:]]


@app.post("/api/chat")
async def chat(req: Request):
    """SSE stream: user sends text (or empty to let the AI open the scene)."""
    body = await req.json()
    sid = body["session_id"]
    text = (body.get("text") or "").strip()
    session = db.get_session(sid)
    if not session:
        return JSONResponse({"error": "no such session"}, status_code=404)
    cfg = llm_config()
    err = llm.not_ready_reason(cfg)
    if err:
        return JSONResponse({"error": err}, status_code=503)

    profile = db.get_profile()
    system = prompts.tutor_system_prompt(
        profile, session["mode"], session["scenario"],
        db.recent_mistakes(), db.recent_vocab(),
    )

    user_msg_id = None
    if text:
        user_msg_id = db.add_message(sid, "user", text)

    messages = [{"role": "system", "content": system}] + _history(sid)
    if not text and not db.get_messages(sid):
        messages.append({"role": "user", "content":
                         "(Begin now: greet me / open the scene with your first line. "
                         "Do not mention this instruction.)"})

    def gen():
        yield f"data: {json.dumps({'user_message_id': user_msg_id})}\n\n"
        full = []
        try:
            for delta in llm.chat_stream(messages, cfg):
                full.append(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return
        reply = "".join(full).strip()
        mid = db.add_message(sid, "assistant", reply)
        final = {
            "done": True, "message_id": mid,
            "tokens": jp.annotate(reply),
            "romaji": jp.romaji(reply),
        }
        yield f"data: {json.dumps(final)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ------------------------------------------------------- analysis (LLM jobs)

@app.post("/api/correct")
async def correct(req: Request):
    body = await req.json()
    mid = body["message_id"]
    msg = db.get_message(mid)
    if not msg:
        return JSONResponse({"error": "no such message"}, status_code=404)
    level = db.get_profile()["jlpt_level"]
    result = llm.chat_json(
        prompts.CORRECTION_PROMPT.format(level=level, text=msg["text"]),
        llm_config(),
    )
    result.setdefault("has_errors", False)
    result.setdefault("errors", [])
    db.set_message_correction(mid, result)
    if result.get("has_errors"):
        for err in result["errors"][:3]:
            db.add_mistake(msg["session_id"], err)
    return result


@app.post("/api/translate")
async def translate(req: Request):
    body = await req.json()
    if body.get("message_id"):
        msg = db.get_message(body["message_id"])
        if msg and msg.get("translation"):
            return {"translation": msg["translation"]}
        text = msg["text"] if msg else ""
    else:
        text = body.get("text", "")
    result = llm.chat_json(prompts.TRANSLATE_PROMPT.format(text=text),
                           llm_config(), num_predict=200)
    translation = result.get("translation", "")
    if body.get("message_id") and translation:
        db.set_message_translation(body["message_id"], translation)
    return {"translation": translation}


@app.post("/api/hint")
async def hint(req: Request):
    body = await req.json()
    sid = body["session_id"]
    level = db.get_profile()["jlpt_level"]
    history = prompts.build_hint_history(db.get_messages(sid))
    result = llm.chat_json(
        prompts.HINT_PROMPT.format(level=level,
                                   level_guide=prompts.LEVEL_GUIDE.get(level, ""),
                                   history=history),
        llm_config(), num_predict=400,
    )
    suggestions = result.get("suggestions", [])[:3]
    for s in suggestions:
        s["romaji"] = jp.romaji(s.get("japanese", ""))
    return {"suggestions": suggestions}


_POS_LABELS = {
    "n": "noun", "v1": "ichidan verb", "v5": "godan verb", "adj-i": "い-adjective",
    "adj-na": "な-adjective", "adv": "adverb", "exp": "expression", "prt": "particle",
    "int": "interjection", "ctr": "counter", "aux-v": "auxiliary verb", "pn": "pronoun",
}


@app.post("/api/word")
async def word(req: Request):
    body = await req.json()
    w = body.get("word", "").strip()
    sentence = body.get("sentence", "")
    info = jp.word_info(w)

    # 1) JMdict: instant + accurate. Try surface form, then dictionary form.
    entry = dictionary.lookup(w, info["reading"])
    lemma = jp.lemma_of(w)
    conjugated = False
    if not entry and lemma and lemma != w:
        entry = dictionary.lookup(lemma)
        conjugated = entry is not None
    if entry:
        if conjugated:  # show reading of what they clicked, not the lemma
            entry = {**entry, "reading": info["reading"]}
        pos = entry.get("pos") or ""
        pos_label = ", ".join(_POS_LABELS.get(p, p) for p in pos.split(",") if p)
        notes = pos_label
        if lemma and lemma != w:
            notes = f"dictionary form: {lemma}" + (f" · {pos_label}" if pos_label else "")
        return {
            "word": w, "reading": entry["reading"] or info["reading"],
            "romaji": info["romaji"], "meaning": entry["meaning"],
            "notes": notes, "example": "", "example_en": "",
        }

    # 2) LLM fallback for names/slang/phrases JMdict doesn't know.
    result = llm.chat_json(prompts.WORD_PROMPT.format(word=w, sentence=sentence),
                           llm_config(), num_predict=250)
    return {
        "word": w,
        "reading": info["reading"],
        "romaji": info["romaji"],
        "meaning": result.get("meaning", ""),
        "notes": result.get("notes", ""),
        "example": result.get("example", ""),
        "example_en": result.get("example_en", ""),
    }


@app.post("/api/sessions/{sid}/end")
def end_session(sid: int):
    session = db.get_session(sid)
    if not session:
        return JSONResponse({"error": "no such session"}, status_code=404)
    msgs = db.get_messages(sid)
    level = db.get_profile()["jlpt_level"]
    transcript = "\n".join(
        f"{'Tutor' if m['role'] == 'assistant' else 'Student'}: {m['text']}" for m in msgs
    )
    corrections = []
    for m in msgs:
        if m.get("correction") and m["correction"].get("has_errors"):
            for e in m["correction"]["errors"]:
                corrections.append(f"{e.get('wrong')} → {e.get('right')} ({e.get('explanation')})")
    summary = {}
    if any(m["role"] == "user" for m in msgs):
        summary = llm.chat_json(
            prompts.SUMMARY_PROMPT.format(level=level, transcript=transcript[-4000:],
                                          corrections="\n".join(corrections) or "none"),
            llm_config(), num_predict=500,
        )
    summary.setdefault("summary", "Session complete — nice work showing up to practice!")
    summary.setdefault("strengths", [])
    summary.setdefault("areas_to_improve", [])
    summary.setdefault("new_words", [])
    for w in summary["new_words"]:
        w.update(jp.word_info(w.get("word", "")))
        entry = dictionary.lookup(w.get("word", "")) or (
            dictionary.lookup(jp.lemma_of(w.get("word", "")) or ""))
        if entry:  # prefer real dictionary glosses over LLM guesses
            w["meaning"] = entry["meaning"]
            w["reading"] = entry["reading"] or w.get("reading", "")
    user_turns = sum(1 for m in msgs if m["role"] == "user")
    summary["stats"] = {"turns": user_turns, "corrections": len(corrections)}
    db.end_session(sid, summary)
    return summary


@app.get("/api/backup/status")
def backup_status():
    return {
        "freq": setting("backup_freq", "off"),
        "dir": backup.backup_dir(),
        "last": float(setting("backup_last", 0) or 0),
    }


@app.post("/api/backup/now")
def backup_run():
    try:
        return backup.backup_now()
    except Exception as e:
        return JSONResponse({"error": f"Backup failed: {e}"}, status_code=500)


@app.get("/api/backup/export")
def backup_export():
    tmp = backup.export_snapshot()
    name = f"kaiwa-backup-{date.today().isoformat()}.db"
    return FileResponse(tmp, filename=name, media_type="application/octet-stream",
                        background=BackgroundTask(os.remove, tmp))


@app.post("/api/backup/import")
async def backup_import(file: UploadFile = File(...)):
    err = backup.restore_from(await file.read())
    if err:
        return JSONResponse({"error": err}, status_code=400)
    return {"ok": True}


@app.post("/api/reset")
def reset_all_data():
    """Wipe everything back to a fresh install (debug / start over)."""
    try:
        backup.reset_all()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": f"Reset failed: {e}"}, status_code=500)


@app.get("/api/dictionary")
def dictionary_search(q: str = ""):
    return {"results": dictionary.search(q)}


# -------------------------------------------------------------- voice (I/O)

@app.post("/api/stt")
async def api_stt(audio: UploadFile = File(...)):
    if not stt.available():
        return JSONResponse({"error": "whisper-cli or model missing"}, status_code=503)
    data = await audio.read()
    text = stt.transcribe(data)
    return {"text": text}


@app.get("/api/tts")
def api_tts(text: str, voice: str = "", speed: float = 1.0, intonation: float | None = None):
    v = voice or setting("voice") or tts.default_voice()
    into = intonation if intonation is not None else float(setting("intonation") or 1.0)
    try:
        wav = tts.synthesize(text, v, speed, into)
    except Exception:
        wav = tts.synthesize(text, "say:Kyoko", speed)  # engine fallback
    if not wav:
        return JSONResponse({"error": "tts failed"}, status_code=500)
    return Response(content=wav, media_type="audio/wav",
                    headers={"Cache-Control": "max-age=86400"})


# -------------------------------------------------------------- vocab & SRS

@app.get("/api/vocab")
def vocab_list():
    return {"vocab": db.list_vocab()}


def _root_form(b: dict) -> dict:
    """Store dictionary forms, not conjugations/particles (食べました → 食べる).

    Only swaps when JMdict confirms the lemma, so we never trade a real word
    for a bad tokenizer guess.
    """
    w = (b.get("word") or "").strip()
    b = {**b, "word": w}
    if not w or dictionary.lookup(w):  # already a dictionary form
        return b
    # Conjugated verbs/adjectives want the lemma (食べました → 食べる); anything
    # else wants the first-token surface, which keeps the user's orthography
    # while shedding trailing particles (ご飯を → ご飯, not the lemma's 御飯).
    toks = jp.annotate(w)
    first = toks[0]["surface"] if toks else ""
    cands = (jp.lemma_of(w), first) if toks and toks[0]["pos"] in ("動詞", "形容詞") \
        else (first, jp.lemma_of(w))
    for cand in cands:
        if not cand or cand == w:
            continue
        info = jp.word_info(cand)
        entry = dictionary.lookup(cand, info["reading"])
        if entry:
            return {**b, "word": cand, "reading": entry["reading"] or info["reading"],
                    "romaji": info["romaji"], "meaning": entry["meaning"]}
    return b


@app.post("/api/vocab")
async def vocab_add(req: Request):
    b = _root_form(await req.json())
    row = db.add_vocab(b["word"], b.get("reading", ""), b.get("romaji", ""),
                       b.get("meaning", ""), b.get("example", ""), b.get("example_en", ""))
    return row


@app.delete("/api/vocab/{vid}")
def vocab_delete(vid: int):
    db.delete_vocab(vid)
    return {"ok": True}


@app.get("/api/srs/due")
def srs_due():
    return {"due": db.srs_due()}


@app.post("/api/srs/review")
async def srs_review(req: Request):
    b = await req.json()
    return db.srs_review(b["vocab_id"], int(b["grade"]))


# ---------------------------------------------------------------- dashboard

@app.get("/api/dashboard")
def dashboard():
    return db.dashboard()
