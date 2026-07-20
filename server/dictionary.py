"""Local JMdict dictionary: fast, accurate word lookups (no LLM needed).

Builds data/jmdict.db (SQLite) once from models/jmdict-eng-*.json.
"""
import glob
import json
import os
import sqlite3

from . import paths

DB = os.path.join(paths.DATA_DIR, "jmdict.db")


def _source_json() -> str | None:
    # Ships bundled inside the installed app (paths.BUNDLED_MODELS_DIR); in dev
    # both dirs point at the repo's models/. A user-dropped copy wins if present.
    hits = []
    for d in (paths.MODELS_DIR, paths.BUNDLED_MODELS_DIR):
        hits += glob.glob(os.path.join(d, "jmdict-eng-*.json"))
    return sorted(hits)[-1] if hits else None


def available() -> bool:
    return os.path.exists(DB) or _source_json() is not None


def build_if_needed():
    if os.path.exists(DB) or not _source_json():
        return
    src = _source_json()
    print(f"[dictionary] building {DB} from {os.path.basename(src)} …")
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        form TEXT NOT NULL,          -- kanji or kana writing
        reading TEXT,                -- primary kana reading
        gloss TEXT NOT NULL,         -- '; '-joined senses
        pos TEXT,
        common INTEGER DEFAULT 0
    )""")
    rows = []
    for w in data["words"]:
        kanji = [k["text"] for k in w.get("kanji", [])]
        kana = [k["text"] for k in w.get("kana", [])]
        common = any(k.get("common") for k in w.get("kanji", []) + w.get("kana", []))
        reading = kana[0] if kana else ""
        senses = []
        pos = ""
        for s in w.get("sense", [])[:3]:
            glosses = [g["text"] for g in s.get("gloss", [])[:4]]
            if glosses:
                senses.append(", ".join(glosses))
            if not pos and s.get("partOfSpeech"):
                pos = ",".join(s["partOfSpeech"][:2])
        if not senses:
            continue
        gloss = "; ".join(senses)
        for form in set(kanji + kana):
            rows.append((form, reading, gloss, pos, int(common)))
    con.executemany(
        "INSERT INTO entries (form, reading, gloss, pos, common) VALUES (?,?,?,?,?)", rows)
    con.execute("CREATE INDEX idx_form ON entries(form)")
    con.commit()
    con.close()
    print(f"[dictionary] done: {len(rows)} forms indexed")


_con = None


def _conn():
    global _con
    if _con is None:
        build_if_needed()
        if not os.path.exists(DB):
            return None
        _con = sqlite3.connect(DB, check_same_thread=False)
        _con.row_factory = sqlite3.Row
    return _con


def _is_japanese(q: str) -> bool:
    return any("぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" for ch in q)


def search(query: str, limit: int = 30) -> list:
    """Dictionary-tab search: Japanese → prefix match on forms, English → gloss match."""
    con = _conn()
    q = (query or "").strip()
    if con is None or not q:
        return []
    if _is_japanese(q):
        rows = con.execute(
            "SELECT * FROM entries WHERE form LIKE ? "
            "ORDER BY (form=?) DESC, common DESC, length(form) LIMIT ?",
            (q + "%", q, limit * 2)).fetchall()
    else:
        if len(q) < 2:
            return []
        lq = q.lower()
        # rank word-boundary hits first so "sushi" beats "T·sushi·ma cat"
        rows = con.execute(
            "SELECT * FROM entries WHERE gloss LIKE ? "
            "ORDER BY ((' ' || lower(gloss)) LIKE ('% ' || ? || '%')) DESC, "
            "common DESC, instr(lower(gloss), ?), length(gloss) LIMIT ?",
            ("%" + q + "%", lq, lq, limit * 2)).fetchall()
    out, seen = [], set()
    for r in rows:
        key = (r["form"], r["gloss"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"form": r["form"], "reading": r["reading"], "meaning": r["gloss"],
                    "pos": r["pos"], "common": bool(r["common"])})
        if len(out) >= limit:
            break
    return out


def lookup(word: str, reading: str | None = None) -> dict | None:
    """Exact-form lookup; prefers common entries.

    `reading` (hiragana) disambiguates homographs: 本 is ほん "book" or
    もと "origin" — without it you get whichever JMdict ranks first.
    """
    con = _conn()
    if con is None or not word:
        return None
    rows = con.execute(
        "SELECT * FROM entries WHERE form=? ORDER BY common DESC LIMIT 10", (word,)
    ).fetchall()
    if not rows:
        return None
    best = rows[0]
    if reading:
        best = next((r for r in rows if r["reading"] == reading), best)
    return {"meaning": best["gloss"], "reading": best["reading"],
            "pos": best["pos"], "common": bool(best["common"])}
