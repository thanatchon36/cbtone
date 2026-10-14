# ruff: noqa: RUF001
"""Entity masking for contamination-aware evaluation (MISSION.md §3, paper §Contamination).

Replaces bank names, countries/regions, currencies, dates and numeric rate levels with
placeholders so a scorer cannot rely on memorised meeting outcomes. Generic words such as
"inflation", "growth" and "Committee" are left untouched. Idempotent.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from cbtone.schema import Language

_FLAGS = re.IGNORECASE


def _alt(words: Iterable[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


_BANKS = _alt(
    [
        "Federal Open Market Committee",
        "Federal Reserve Board",
        "Federal Reserve System",
        "Federal Reserve",
        "European Central Bank",
        "Bank of England",
        "Reserve Bank of Australia",
        "Monetary Authority of Singapore",
        "Bank Indonesia",
        "Bank Negara Malaysia",
        "People's Bank of China",
        "Bank of Thailand",
        "Eurosystem",
        "中国人民银行",
        "美联储",
        "欧洲央行",
        "英格兰银行",
        "新加坡金融管理局",
        "ธนาคารแห่งประเทศไทย",
    ]
)
_BANK_ACRONYMS = "FOMC|ECB|BoE|BOE|RBA|MAS|BNM|PBoC|PBOC|PBC|BoT|BOT"

_COUNTRIES = _alt(
    [
        "United States",
        "United Kingdom",
        "Great Britain",
        "Singapore",
        "Indonesia",
        "Malaysia",
        "Thailand",
        "China",
        "Australia",
        "Britain",
        "euro area",
        "euro zone",
        "eurozone",
        "Euro area",
        "Europe",
        "ASEAN",
        "Asia-Pacific",
        "Asia",
        "Singaporean",
        "Indonesian",
        "Malaysian",
        "Thai",
        "Chinese",
        "Australian",
        "British",
        "Amerika Serikat",
        "Inggris",
        "Singapura",
        "Tiongkok",
        "Britania Raya",
        "Eropa",
        "Australia",
        "Thailand",
        "美国",
        "中国",
        "新加坡",
        "马来西亚",
        "印度尼西亚",
        "泰国",
        "澳大利亚",
        "英国",
        "欧元区",
        "欧洲",
        "ประเทศไทย",
        "สหรัฐฯ",
    ]
)
_COUNTRY_ACRONYMS = "US|USA|UK|EU"

_CURRENCY_PHRASES = _alt(
    [
        "Singapore dollars?",
        "Australian dollars?",
        "U.S. dollars?",
        "US dollars?",
        "Hong Kong dollars?",
        "pounds? sterling",
        "Thai baht",
        "Malaysian ringgit",
        "Indonesian rupiah",
        "Chinese yuan",
    ]
).replace(r"\?", "?")
_CURRENCY_WORDS = _alt(
    ["rupiah", "ringgit", "baht", "yuan", "renminbi", "euros?", "sterling", "rupiahs"]
).replace(r"\?", "?")
_CURRENCY_CODES = "SGD|IDR|MYR|THB|CNY|CNH|RMB|USD|EUR|GBP|AUD"

_MONTHS_NO_MAY = (
    "January|February|March|April|June|July|August|September|October|November|December|"
    "Januari|Februari|Maret|Mei|Juni|Juli|Agustus|Oktober|Desember|"
    "Mac|Jun|Julai|Ogos|Disember"
)
_MONTH = rf"(?:(?:{_MONTHS_NO_MAY})\b|May(?=\s+\d)|(?<=\d\s)May\b|(?<=\d)May\b)"
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_YEAR = r"(?:19|20)\d{2}"

_NUM = r"(?:\d+-\d\s?[/⁄]\s?\d|\d+(?:[.,]\d+)?(?:\s?[¼½¾⅛-⅞]|\s\d\s?[/⁄]\s?\d)?|[¼½¾⅛-⅞]|\d\s?[/⁄]\s?\d)"
_NUM_RANGE = rf"{_NUM}(?:\s?(?:-|–|to|and|hingga|sampai|sehingga|至|到)\s?{_NUM})?"
_PCT_UNIT = (
    r"(?:\s?%|\s?％|\s?(?:percentage\s+points?|per\s?cent|percent|persen|peratus)\b"
    r"|\s?个?百分点|\s?เปอร์เซ็นต์)"
)
_BP_UNIT = (
    r"(?:[-\s]?(?:basis[-\s]points?|bps|bpts?|bp)\b|\s?(?:poin dasar|mata asas)\b"
    r"|\s?个?基点|\s?บีบีเอส)"
)
_FRACTION_WORDS = (
    r"\b(?:quarter|half|three[-\s]quarters?)(?:[-\s]|\s+of\s+a\s+)"
    r"(?:percentage\s+)?point\b"
)

# Named policy instruments and decision bodies identify the bank as surely as its name does
# (review, 2026-10-14, before any masked scoring). Generic framework words that carry the policy
# meaning itself ("policy band", "slope", "the Committee", "policy rate") are kept.
_INSTRUMENTS = _alt(
    [
        "federal funds rate",
        "fed funds rate",
        "Overnight Policy Rate",
        "BI 7-Day Reverse Repo Rate",
        "BI 7-Day Repo Rate",
        "BI-Rate",
        "BI Rate",
        "BI7DRR",
        "cash rate target",
        "cash rate",
        "deposit facility rate",
        "main refinancing operations rate",
        "main refinancing rate",
        "marginal lending facility rate",
        "Kadar Dasar Semalaman",
        "Loan Prime Rate",
        "贷款市场报价利率",
    ]
)
_COMMITTEES = _alt(
    [
        "Governing Council",
        "Monetary Policy Committee",
        "Reserve Bank Board",
        "Monetary Policy Board",
        "Board of Governors",
        "Rapat Dewan Gubernur",
        "Dewan Gubernur",
        "Jawatankuasa Dasar Monetari",
        "货币政策委员会",
        "คณะกรรมการนโยบายการเงิน",
    ]
)

# (pattern, replacement), applied in order. Placeholders are upper-case in brackets, which no
# pattern below matches, so masking is idempotent.
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"(?:{_INSTRUMENTS})", _FLAGS), "[POLICY_RATE]"),
    (re.compile(r"\bBank Rate\b|\bOPR\b|\bLPR\b"), "[POLICY_RATE]"),
    (re.compile(rf"(?:{_COMMITTEES})", _FLAGS), "[COMMITTEE]"),
    (re.compile(r"\bMPC\b|กนง\."), "[COMMITTEE]"),
    (re.compile(r"\bFed\b"), "[BANK]"),
    (re.compile(rf"(?:{_BANKS})", _FLAGS), "[BANK]"),
    (re.compile(rf"\b(?:{_BANK_ACRONYMS})\b"), "[BANK]"),
    (re.compile(r"\bS\$NEER\b"), "[CURRENCY] NEER"),
    (re.compile(rf"\b(?:{_CURRENCY_PHRASES})\b", _FLAGS), "[CURRENCY]"),
    (re.compile(rf"\b(?:{_COUNTRIES})\b", _FLAGS), "[COUNTRY]"),
    (re.compile(r"(?<![\w])(?:U\.S\.A?\.?|U\.K\.)(?!\w)"), "[COUNTRY]"),
    (re.compile(rf"\b(?:{_COUNTRY_ACRONYMS})\b"), "[COUNTRY]"),
    (re.compile(r"(?:美国|中国|新加坡|欧元区|欧洲|英国)"), "[COUNTRY]"),
    (re.compile(rf"\b(?:{_CURRENCY_WORDS})\b", _FLAGS), "[CURRENCY]"),
    (re.compile(r"\b(?:Rp|RM)\.?(?=\s?\d)"), "[CURRENCY]"),
    (re.compile(r"\b[SA]?\$|£|€|¥|元(?=\b)"), "[CURRENCY]"),
    (re.compile(rf"\b(?:{_CURRENCY_CODES})\b"), "[CURRENCY]"),
    (re.compile(rf"{_FRACTION_WORDS}", _FLAGS), "[RATE]"),
    (re.compile(rf"{_NUM_RANGE}{_BP_UNIT}", _FLAGS), "[BP]"),
    (re.compile(rf"{_NUM_RANGE}{_PCT_UNIT}", _FLAGS), "[RATE]"),
    # Dates: quarters, then full dates, then bare years.
    (re.compile(rf"\b{_YEAR}\s?Q[1-4]\b|\bQ[1-4]\s?{_YEAR}\b|\bQ[1-4]\b"), "[DATE]"),
    (
        re.compile(
            r"\d{4}\s?年(?:\d{1,2}\s?月(?:\d{1,2}\s?[日号])?)?|\d{1,2}\s?月(?:\d{1,2}\s?[日号])?"
        ),
        "[DATE]",
    ),
    (
        re.compile(
            rf"(?:\b{_DAY}\s+)?{_MONTH}(?:\s+{_DAY}\b)?(?:,?\s+{_YEAR}\b)?"
            rf"|\b(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?(?=\s+\d)(?:\s+{_DAY}\b)?"
            rf"(?:,?\s+{_YEAR}\b)?"
        ),
        "[DATE]",
    ),
    (re.compile(rf"\b{_YEAR}\b"), "[DATE]"),
]


def mask_entities(text: str, lang: Language = "en") -> str:
    """Replace bank, country, currency, date and rate-level mentions with placeholders.

    Placeholders: ``[BANK]``, ``[COMMITTEE]``, ``[POLICY_RATE]``, ``[COUNTRY]``, ``[CURRENCY]``,
    ``[DATE]``, ``[RATE]``, ``[BP]``.
    All language patterns (en/id/ms/zh/th) are applied regardless of ``lang``, because
    documents routinely mix scripts; ``lang`` is accepted for API stability.
    """
    del lang
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return text
