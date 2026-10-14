# ruff: noqa: RUF001, SIM905
"""Paragraph and sentence splitting for en/id/ms/zh/th (MISSION.md §1.1, §3).

pysbd has no Indonesian, Malay or Thai rules, so Latin-script languages share one
regex splitter with an abbreviation list; zh is character-level; th uses pythainlp.
"""

from __future__ import annotations

import re
import warnings

from cbtone.schema import Language

_PARA_BREAK = re.compile(r"\n\s*\n")

# Never end a sentence (titles, citations, currency and month abbreviations).
_HARD_ABBREV = frozenset(
    """mr. mrs. ms. dr. prof. no. nos. vs. cf. e.g. i.e. approx. fig. st. jr. sr. gen. gov.
    sen. rep. hon. rp. bhd. sdn. tn. pn. ir. drs. hj. jan. feb. mar. apr. jun. jul. aug. sep.
    sept. oct. nov. dec. ogos. approx est. ca. ed. vol. pp. p. q.""".split()
)
# Abbreviations that may also close a sentence: split only before a typical sentence opener.
_WEAK_ABBREV = frozenset(
    """etc. inc. ltd. co. corp. plc. tbk. dll. dsb. dkk. u.s. u.k. u.s.a. a.m. p.m. dst.""".split()
)
_STARTERS = frozenset(
    """the it in this these those we they he she a an at on as for however if but and while
    although there our its with by from to of after before since during despite overall
    in  dalam pada ini itu namun sementara selain kami bank""".split()
)

_BOUNDARY = re.compile(r"[.!?]+[\"'”’)\]]*\s+")
_OPENER = re.compile(r"[A-Z0-9\"'“‘(\[¿]")
_INITIAL = re.compile(r"^[A-Za-z]\.$")
_DOTTED = re.compile(r"^(?:[A-Za-z]{1,2}\.){2,}$")
_SMALL_NUM = re.compile(r"^\d{1,2}\.$")
_CLOSERS = "\"'”’)」』）]"
_ZH_END = "。！？；!?;"
_ZH_CLOSE_RE = re.escape(_CLOSERS)
_ZH_SENT = re.compile(
    rf"[^{_ZH_END}]+(?:[{_ZH_END}]+[{_ZH_CLOSE_RE}]*)?|[{_ZH_END}]+[{_ZH_CLOSE_RE}]*"
)


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; strip and drop empty paragraphs."""
    return [p.strip() for p in _PARA_BREAK.split(text.replace("\r\n", "\n")) if p.strip()]


def _split_latin(para: str) -> list[str]:
    text = re.sub(r"\s+", " ", para).strip()
    out: list[str] = []
    start = 0
    for m in _BOUNDARY.finditer(text):
        rest = text[m.end() :]
        if not rest or not _OPENER.match(rest):
            continue
        head = text[start : m.end()].rstrip()
        term = m.group(0).strip()
        if term[0] == "." and len(term.rstrip(_CLOSERS)) == 1:
            tok = head.rsplit(" ", 1)[-1].rstrip(_CLOSERS).lstrip("([\"'“‘")
            low = tok.lower()
            if low in _HARD_ABBREV or _INITIAL.match(tok) or _SMALL_NUM.match(tok):
                continue
            if low in _WEAK_ABBREV or _DOTTED.match(tok):
                nxt = re.match(r"[\w']+", rest)
                if not nxt or nxt.group(0).lower() not in _STARTERS:
                    continue
        out.append(head)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def _split_zh(para: str) -> list[str]:
    out: list[str] = []
    for line in para.splitlines():
        out.extend(m.group(0).strip() for m in _ZH_SENT.finditer(line) if m.group(0).strip())
    return out


def _split_th(para: str) -> list[str]:
    try:
        from pythainlp.tokenize import sent_tokenize

        raw = sent_tokenize(para, engine="crfcut")  # needs pythainlp + python-crfsuite
    except ImportError:
        warnings.warn(
            "pythainlp/python-crfsuite not installed (pip install 'cbtone[thai]'); "
            "falling back to whitespace splitting for Thai",
            stacklevel=3,
        )
        return [s for s in re.split(r"\s+", para) if s]
    sents: list[str] = [raw] if isinstance(raw, str) else [str(x) for x in raw]
    return [s.strip() for s in sents if s.strip()]


def split_sentences(text: str, lang: Language) -> list[str]:
    """Split ``text`` into sentences, paragraph by paragraph (no sentence crosses a blank line)."""
    out: list[str] = []
    for para in split_paragraphs(text):
        if lang == "zh":
            out.extend(_split_zh(para))
        elif lang == "th":
            out.extend(_split_th(para))
        else:
            out.extend(_split_latin(para))
    return out
