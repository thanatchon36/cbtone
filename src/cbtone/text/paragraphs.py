"""Rule-based paragraph typing and the pre-registered scorer input (RESEARCH_QUESTIONS.md §0.5).

``tag_paragraph`` assigns one of decision / forward_guidance / outlook / risks / boilerplate /
other from language-specific cue lists (en, id, ms, th, zh). ``policy_text`` builds the text every
scorer reads: paragraphs tagged decision, forward_guidance, outlook, risks — chosen in that
priority until the character cap is reached, then emitted in document order. With no tagged
paragraph, the first ``cap`` characters are used.
"""

from __future__ import annotations

import re
from typing import Literal

from cbtone.schema import Document
from cbtone.text.split import split_paragraphs

Tag = Literal["decision", "forward_guidance", "outlook", "risks", "boilerplate", "other"]
PRIORITY: tuple[Tag, ...] = ("decision", "forward_guidance", "outlook", "risks")
MIN_TAIL = 200  # a truncated last paragraph is kept only if at least this many chars fit

_CUES: dict[str, dict[Tag, tuple[str, ...]]] = {
    "en": {
        "decision": (
            r"decided to", r"\bdecision\b", r"\bvoted\b", r"policy rate", r"target range",
            r"federal funds", r"cash rate", r"bank rate", r"\bOPR\b", r"BI-Rate",
            r"policy band", r"S\$NEER", r"basis points?", r"key (?:ECB )?interest rates",
            r"deposit facility", r"(?:raise|lower|reduce|increase|maintain|keep|leave)\w*\s+"
            r"(?:the\s+)?(?:\w+\s+){0,3}(?:rate|band|slope|target)",
            r"\bunchanged\b",
        ),
        "forward_guidance": (
            r"expects? to", r"anticipates?", r"will continue to", r"remains? appropriate",
            r"coming (?:months|quarters|meetings)", r"data[- ]dependent", r"stands? ready",
            r"will (?:closely )?monitor", r"remains? vigilant", r"for some time",
            r"extended period", r"going forward", r"in the period ahead", r"future (?:policy|decisions)",
            r"further (?:tightening|easing|adjustments?)",
        ),
        "outlook": (
            r"\binflation\b", r"\bgrowth\b", r"\beconomy\b", r"\bprojected\b", r"\bforecasts?\b",
            r"expected to", r"\boutlook\b", r"\bGDP\b", r"labou?r market", r"unemployment",
            r"\bdemand\b", r"\bwages?\b", r"\bprices?\b",
        ),
        "risks": (
            r"\brisks?\b", r"uncertaint", r"downside", r"upside", r"vulnerab", r"geopolit",
            r"\btail\b",
        ),
    },
    "id": {
        "decision": (
            r"memutuskan", r"mempertahankan", r"menaikkan", r"menurunkan", r"BI-Rate",
            r"suku bunga", r"Rapat Dewan Gubernur", r"basis poin", r"\bbps\b",
        ),
        "forward_guidance": (r"ke depan", r"akan terus", r"akan tetap", r"tetap waspada"),
        "outlook": (r"inflasi", r"pertumbuhan ekonomi", r"diperkirakan", r"prakiraan", r"permintaan"),
        "risks": (r"risiko", r"ketidakpastian"),
    },
    "ms": {
        "decision": (
            r"memutuskan", r"mengekalkan", r"menaikkan", r"menurunkan", r"\bOPR\b",
            r"Kadar Dasar Semalaman", r"mata asas",
        ),
        "forward_guidance": (r"akan terus", r"pada masa hadapan", r"ke hadapan", r"kekal sesuai"),
        "outlook": (r"inflasi", r"pertumbuhan", r"dijangka", r"unjuran", r"permintaan"),
        "risks": (r"risiko", r"ketidaktentuan"),
    },
    "th": {
        "decision": (r"มีมติ", r"อัตราดอกเบี้ยนโยบาย", r"คงอัตรา", r"ลดอัตรา", r"ขึ้นอัตรา"),
        "forward_guidance": (r"ระยะต่อไป", r"จะติดตาม", r"พร้อมปรับ"),
        "outlook": (r"เงินเฟ้อ", r"เศรษฐกิจ", r"คาดว่า", r"ขยายตัว"),
        "risks": (r"ความเสี่ยง", r"ความไม่แน่นอน"),
    },
    "zh": {
        "decision": (r"决定", r"利率", r"降准", r"下调", r"上调", r"货币政策"),
        "forward_guidance": (r"下一阶段", r"将继续", r"保持"),
        "outlook": (r"经济", r"通胀", r"物价", r"预计", r"增长"),
        "risks": (r"风险", r"不确定"),
    },
}
_BOILERPLATE = re.compile(
    r"press conference will|will be published|for (?:further|more) information|media enquir|"
    r"\bcontact\b|\btel\b|e-?mail|©|copyright|all rights reserved|voting for (?:the|this)|"
    r"implementation note|minutes of the meeting will|lihat juga|see also|"
    r"informasi lebih lanjut|untuk maklumat lanjut",
    re.I,
)
_COMPILED = {
    lang: {tag: re.compile("|".join(pats), re.I) for tag, pats in cues.items()}
    for lang, cues in _CUES.items()
}


def tag_paragraph(text: str, lang: str = "en") -> Tag:
    """Most-cued category; ties go to the earlier one in ``PRIORITY``."""
    if len(text) < 400 and _BOILERPLATE.search(text):
        return "boilerplate"
    cues = _COMPILED.get(lang, _COMPILED["en"])
    hits = {tag: len(rx.findall(text)) for tag, rx in cues.items()}
    best = max(hits.values(), default=0)
    if best == 0:
        return "other"
    return next(t for t in PRIORITY if hits.get(t, 0) == best)


def paragraphs_of(doc: Document) -> list[str]:
    if doc.sections:
        return [s.text for s in doc.sections if s.text.strip()]
    return split_paragraphs(doc.text)


def select_policy_paragraphs(paras: list[str], lang: str, cap: int) -> list[str]:
    """Indices chosen by priority under ``cap``, returned in document order."""
    tags = [tag_paragraph(p, lang) for p in paras]
    chosen: dict[int, str] = {}
    used = 0
    for tag in PRIORITY:
        for i, (p, t) in enumerate(zip(paras, tags, strict=True)):
            if t != tag:
                continue
            room = cap - used
            if room <= 0:
                break
            if len(p) <= room:
                chosen[i] = p
                used += len(p) + 1
            elif room >= MIN_TAIL:
                chosen[i] = p[:room].rsplit(" ", 1)[0]
                used = cap
    return [chosen[i] for i in sorted(chosen)]


def policy_text(doc: Document, cap: int = 6000) -> str:
    """The pre-registered scorer input for ``doc`` (RESEARCH_QUESTIONS.md §0.5)."""
    paras = paragraphs_of(doc)
    picked = select_policy_paragraphs(paras, doc.language, cap)
    if picked:
        return "\n".join(picked)
    return doc.text[:cap]
