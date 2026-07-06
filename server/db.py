"""SQLite persistence for Kaiwa: profile, sessions, messages, vocab (SRS), mistakes."""
import json
import os
import sqlite3
import time
from datetime import date, datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kaiwa.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT DEFAULT '',
    jlpt_level TEXT DEFAULT 'N5',
    goals TEXT DEFAULT '',
    interests TEXT DEFAULT '',
    settings TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    scenario_id TEXT,
    scenario TEXT,             -- JSON of scenario/custom roleplay used
    started_at REAL NOT NULL,
    ended_at REAL,
    summary TEXT               -- JSON summary
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    translation TEXT,
    correction TEXT,           -- JSON correction result (user messages)
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS vocab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE,
    reading TEXT,
    romaji TEXT,
    meaning TEXT,
    example TEXT,
    example_en TEXT,
    added_at REAL NOT NULL,
    -- SM-2 spaced repetition state
    ease REAL DEFAULT 2.5,
    interval_days REAL DEFAULT 0,
    due_at REAL NOT NULL,
    reps INTEGER DEFAULT 0,
    lapses INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    original TEXT,
    corrected TEXT,
    explanation TEXT,
    category TEXT,
    ts REAL NOT NULL
);
"""


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.executescript(SCHEMA)
        c.execute("INSERT OR IGNORE INTO profile (id) VALUES (1)")


# ------------------------------------------------------------------ profile

def get_profile() -> dict:
    with _conn() as c:
        r = c.execute("SELECT * FROM profile WHERE id=1").fetchone()
        d = dict(r)
        d["settings"] = json.loads(d.get("settings") or "{}")
        return d


def update_profile(fields: dict):
    allowed = {"name", "jlpt_level", "goals", "interests"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
        elif k == "settings":
            sets.append("settings=?")
            vals.append(json.dumps(v))
    if not sets:
        return
    with _conn() as c:
        c.execute(f"UPDATE profile SET {', '.join(sets)} WHERE id=1", vals)


def get_setting(key: str, default=None):
    return get_profile()["settings"].get(key, default)


def set_settings(patch: dict):
    p = get_profile()
    p["settings"].update(patch)
    update_profile({"settings": p["settings"]})


# ----------------------------------------------------------------- sessions

def create_session(mode: str, scenario_id: str | None, scenario: dict | None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO sessions (mode, scenario_id, scenario, started_at) VALUES (?,?,?,?)",
            (mode, scenario_id, json.dumps(scenario) if scenario else None, time.time()),
        )
        return cur.lastrowid


def get_session(sid: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["scenario"] = json.loads(d["scenario"]) if d["scenario"] else None
        d["summary"] = json.loads(d["summary"]) if d["summary"] else None
        return d


def end_session(sid: int, summary: dict):
    with _conn() as c:
        c.execute("UPDATE sessions SET ended_at=?, summary=? WHERE id=?",
                  (time.time(), json.dumps(summary), sid))


def add_message(sid: int, role: str, text: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO messages (session_id, role, text, ts) VALUES (?,?,?,?)",
            (sid, role, text, time.time()),
        )
        return cur.lastrowid


def get_messages(sid: int) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id", (sid,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["correction"] = json.loads(d["correction"]) if d["correction"] else None
            out.append(d)
        return out


def get_message(mid: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        return dict(r) if r else None


def set_message_translation(mid: int, translation: str):
    with _conn() as c:
        c.execute("UPDATE messages SET translation=? WHERE id=?", (translation, mid))


def set_message_correction(mid: int, correction: dict):
    with _conn() as c:
        c.execute("UPDATE messages SET correction=? WHERE id=?",
                  (json.dumps(correction), mid))


# ----------------------------------------------------------------- mistakes

def add_mistake(sid: int, err: dict):
    with _conn() as c:
        c.execute(
            "INSERT INTO mistakes (session_id, original, corrected, explanation, category, ts) VALUES (?,?,?,?,?,?)",
            (sid, err.get("wrong", ""), err.get("right", ""),
             err.get("explanation", ""), err.get("category", "other"), time.time()),
        )


def recent_mistakes(limit=8) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT original, corrected, explanation, category FROM mistakes ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def mistake_stats() -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT category, COUNT(*) n FROM mistakes GROUP BY category ORDER BY n DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# -------------------------------------------------------------------- vocab

def add_vocab(word: str, reading: str, romaji_: str, meaning: str,
              example: str = "", example_en: str = "") -> dict:
    with _conn() as c:
        c.execute(
            """INSERT INTO vocab (word, reading, romaji, meaning, example, example_en, added_at, due_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(word) DO UPDATE SET meaning=excluded.meaning,
                   example=excluded.example, example_en=excluded.example_en""",
            (word, reading, romaji_, meaning, example, example_en, time.time(), time.time()),
        )
        r = c.execute("SELECT * FROM vocab WHERE word=?", (word,)).fetchone()
        return dict(r)


def list_vocab() -> list:
    with _conn() as c:
        rows = c.execute("SELECT * FROM vocab ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]


def delete_vocab(vid: int):
    with _conn() as c:
        c.execute("DELETE FROM vocab WHERE id=?", (vid,))


def recent_vocab(limit=10) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT word, meaning FROM vocab ORDER BY added_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------- SRS

def srs_due() -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM vocab WHERE due_at <= ? ORDER BY due_at LIMIT 30",
            (time.time(),),
        ).fetchall()
        return [dict(r) for r in rows]


def srs_review(vid: int, grade: int) -> dict:
    """SM-2. grade: 0=again 1=hard 2=good 3=easy."""
    with _conn() as c:
        r = c.execute("SELECT * FROM vocab WHERE id=?", (vid,)).fetchone()
        if not r:
            return {}
        ease, interval, reps, lapses = r["ease"], r["interval_days"], r["reps"], r["lapses"]
        if grade == 0:
            lapses += 1
            reps = 0
            interval = 0
            ease = max(1.3, ease - 0.2)
            due = time.time() + 60 * 10          # again in 10 min
        else:
            q = {1: 3, 2: 4, 3: 5}[grade]
            ease = max(1.3, ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
            reps += 1
            if reps == 1:
                interval = 1
            elif reps == 2:
                interval = 3 if grade >= 2 else 2
            else:
                mult = {1: 1.2, 2: ease, 3: ease * 1.3}[grade]
                interval = max(interval * mult, interval + 1)
            due = time.time() + interval * 86400
        c.execute(
            "UPDATE vocab SET ease=?, interval_days=?, reps=?, lapses=?, due_at=? WHERE id=?",
            (ease, interval, reps, lapses, due, vid),
        )
        return {"next_due_days": round(max(interval, 0.007), 2)}


# ---------------------------------------------------------------- dashboard

def dashboard() -> dict:
    with _conn() as c:
        sessions = c.execute(
            "SELECT id, mode, scenario, started_at, ended_at, summary FROM sessions "
            "WHERE ended_at IS NOT NULL ORDER BY id DESC"
        ).fetchall()
        total_seconds = sum((s["ended_at"] - s["started_at"]) for s in sessions)
        n_vocab = c.execute("SELECT COUNT(*) n FROM vocab").fetchone()["n"]
        n_mistakes = c.execute("SELECT COUNT(*) n FROM mistakes").fetchone()["n"]
        n_msgs = c.execute("SELECT COUNT(*) n FROM messages WHERE role='user'").fetchone()["n"]
        due = c.execute("SELECT COUNT(*) n FROM vocab WHERE due_at <= ?",
                        (time.time(),)).fetchone()["n"]

        # streak: consecutive days (ending today or yesterday) with a session
        days = sorted({date.fromtimestamp(s["started_at"]) for s in sessions}, reverse=True)
        streak = 0
        if days:
            cursor = date.today()
            if days[0] in (cursor, cursor - timedelta(days=1)):
                cursor = days[0]
                for d in days:
                    if d == cursor:
                        streak += 1
                        cursor -= timedelta(days=1)
                    elif d < cursor:
                        break

        recent = []
        for s in sessions[:8]:
            scen = json.loads(s["scenario"]) if s["scenario"] else None
            summ = json.loads(s["summary"]) if s["summary"] else None
            recent.append({
                "id": s["id"], "mode": s["mode"],
                "title": (scen or {}).get(
                    "title", "Voice Call" if s["mode"] == "call" else "Free Chat"),
                "started_at": s["started_at"],
                "minutes": round((s["ended_at"] - s["started_at"]) / 60, 1),
                "summary": summ,
            })
        return {
            "streak": streak,
            "total_minutes": round(total_seconds / 60),
            "sessions_count": len(sessions),
            "messages_spoken": n_msgs,
            "words_saved": n_vocab,
            "mistakes_logged": n_mistakes,
            "srs_due": due,
            "recent_sessions": recent,
            "mistake_categories": mistake_stats(),
        }
