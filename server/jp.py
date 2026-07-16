"""Japanese text processing: tokenization, furigana (ruby), romaji.

Primary tokenizer: fugashi (MeCab + unidic-lite). Fallback: janome (pure python).
"""
import re
import unicodedata

_KATA_TO_HIRA = str.maketrans(
    {chr(k): chr(k - 0x60) for k in range(0x30A1, 0x30F7)}
)

_kks = None
def _kakasi():
    global _kks
    if _kks is None:
        import pykakasi
        _kks = pykakasi.kakasi()
    return _kks


def kata_to_hira(s: str) -> str:
    return s.translate(_KATA_TO_HIRA)


def has_kanji(s: str) -> bool:
    return any("CJK UNIFIED" in unicodedata.name(c, "") for c in s)


def is_kana(c: str) -> bool:
    return "぀" <= c <= "ヿ" or c in "ーゝゞヽヾ"


# Auxiliaries glue onto the preceding verb/adjective (食べ+まし+た →
# tabemashita) — except standalone copulas, which stay their own word.
_VERBISH = ("動詞", "形容詞", "助動詞", "接尾辞")
_NO_GLUE = ("です", "でしょ", "でしょう", "だ", "だろう")
_PARTICLE_KANA = {"は": "ワ", "へ": "エ", "を": "オ"}


def romaji(text: str) -> str:
    """Hepburn romaji. Tokenize first — kakasi's own segmentation mis-reads
    kanji across word boundaries (ご飯食べた → 'go hanshoku beta').

    Kana is accumulated per output word and romanized whole, so sokuon
    spanning tokens (高かっ+た) still comes out geminated (takakatta).
    """
    try:
        words, prev_pos = [], ""  # words: kana per output word
        for surface, kana, pos in _tokenize(text):
            k = kana or surface
            if pos == "助詞" and surface in _PARTICLE_KANA:
                k = _PARTICLE_KANA[surface]  # は→wa, へ→e, を→o
            if not k.strip():
                prev_pos = pos
                continue
            glue = words and (
                pos in ("補助記号", "記号", "接尾辞")  # punctuation: ね。→ "ne."
                # single-kanji noun suffixes: 日本+語 → nihongo, アメリカ+人 → amerikajin
                or (pos == "名詞" and prev_pos == "名詞" and len(surface) == 1)
                or (prev_pos in _VERBISH
                    and surface not in _NO_GLUE
                    and (pos == "助動詞"
                         or (pos == "助詞" and surface in ("て", "で", "ば", "ちゃ", "じゃ"))))
            )
            if glue:
                words[-1] += k
            else:
                words.append(k)
            prev_pos = pos
        out = []
        for w in words:
            r = "".join(i["hepburn"] for i in _kakasi().convert(w)).strip()
            if r:
                out.append(r)
        return " ".join(out)
    except Exception:
        return ""


# ---------------------------------------------------------------- tokenizers

_tagger = None
_janome = None
_backend = None


def _init_backend():
    global _tagger, _janome, _backend
    if _backend:
        return
    try:
        import fugashi
        _tagger = fugashi.Tagger()
        _backend = "fugashi"
    except Exception:
        from janome.tokenizer import Tokenizer
        _janome = Tokenizer()
        _backend = "janome"


def backend_name() -> str:
    _init_backend()
    return _backend


# UniDic defaults that confuse learners: 私 → ワタクシ, 日本 → ニッポン.
_READING_OVERRIDES = {"私": "ワタシ", "日本": "ニホン"}


def _tokenize(text: str):
    """Yield (surface, reading_katakana_or_None, pos)."""
    _init_backend()
    if _backend == "fugashi":
        prev_pos2 = ""
        for w in _tagger(text):
            kana = _READING_OVERRIDES.get(w.surface)
            pos2 = str(getattr(w.feature, "pos2", "") or "")
            if not kana and w.surface == "人" and prev_pos2 == "固有名詞":
                kana = "ジン"  # unidic-lite says ニン even for 日本人/アメリカ人
            if not kana:
                try:
                    kana = w.feature.kana or w.feature.pron  # unidic: kana reading
                except Exception:
                    pass
            pos = w.feature.pos1 if hasattr(w.feature, "pos1") else ""
            prev_pos2 = pos2
            yield w.surface, kana, str(pos or "")
    else:
        for t in _janome.tokenize(text):
            kana = t.reading if t.reading != "*" else None
            kana = _READING_OVERRIDES.get(t.surface, kana)
            pos = t.part_of_speech.split(",")[0]
            yield t.surface, kana, pos


# ------------------------------------------------------------- ruby aligner

def _ruby_segments(surface: str, reading_hira: str):
    """Align a token's surface with its hiragana reading.

    Returns list of {"t": base_text, "r": ruby_or_None}. Kana runs get no ruby;
    kanji runs get the aligned chunk of the reading.
    """
    # split surface into runs of kana / non-kana
    runs = []
    for ch in surface:
        kind = "kana" if is_kana(ch) else "other"
        if runs and runs[-1][0] == kind:
            runs[-1][1] += ch
        else:
            runs.append([kind, ch])

    if all(k == "kana" for k, _ in runs):
        return [{"t": surface, "r": None}]

    # build regex: kana runs match themselves (in hiragana), other runs -> (.+?)
    pattern = ""
    for kind, run in runs:
        if kind == "kana":
            pattern += re.escape(kata_to_hira(run))
        else:
            pattern += "(.+?)"
    m = re.fullmatch(pattern, reading_hira)
    if not m:
        return [{"t": surface, "r": reading_hira}]

    segs, gi = [], 0
    for kind, run in runs:
        if kind == "kana":
            segs.append({"t": run, "r": None})
        else:
            gi += 1
            segs.append({"t": run, "r": m.group(gi)})
    return segs


def annotate(text: str) -> list:
    """Annotate text into clickable tokens with furigana ruby segments.

    Returns list of tokens:
      {"surface": str, "ruby": [{"t","r"}], "reading": hira, "pos": str, "word": bool}

    Newlines survive as their own non-word tokens (stories are multi-line;
    the tokenizer would otherwise swallow them).
    """
    out = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i:
            out.append({"surface": "\n", "ruby": [{"t": "\n", "r": None}],
                        "reading": None, "pos": "空白", "word": False})
        out.extend(_annotate_line(line))
    return out


def _annotate_line(text: str) -> list:
    out = []
    for surface, kana, pos in _tokenize(text):
        if not surface:
            continue
        reading = kata_to_hira(kana) if kana else None
        is_word = bool(re.search(r"[぀-ヿ一-鿿]", surface)) and pos not in (
            "補助記号", "記号", "空白",
        )
        if reading and has_kanji(surface):
            ruby = _ruby_segments(surface, reading)
        else:
            ruby = [{"t": surface, "r": None}]
        out.append({
            "surface": surface,
            "ruby": ruby,
            "reading": reading if reading else None,
            "pos": pos,
            "word": is_word,
        })
    return out


def kanji_to_kana(text: str) -> str:
    """Rewrite kanji words as their hiragana readings (hiragana-only script mode —
    small local models can't be trusted to obey 'no kanji' on their own)."""
    out = []
    for surface, kana, pos in _tokenize(text):
        if has_kanji(surface) and kana:
            out.append(kata_to_hira(kana))
        else:
            out.append(surface)
    return "".join(out)


def lemma_of(word: str) -> str | None:
    """Dictionary form of the (first word in) `word`, e.g. 食べ → 食べる."""
    _init_backend()
    try:
        if _backend == "fugashi":
            for w in _tagger(word):
                lemma = str(w.feature.lemma or "")
                # unidic lemmas can look like "カード-card" — keep the JP part
                lemma = lemma.split("-")[0]
                return lemma or None
        else:
            for t in _janome.tokenize(word):
                return t.base_form if t.base_form != "*" else None
    except Exception:
        return None
    return None


def word_info(word: str) -> dict:
    """Reading + romaji for a single word."""
    toks = annotate(word)
    reading = "".join((t["reading"] or t["surface"]) for t in toks)
    return {"reading": kata_to_hira(reading), "romaji": romaji(word)}
