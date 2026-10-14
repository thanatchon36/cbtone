"""Dictionary (word-count) scorer, ``scorer_id="dict-v1"`` (docs/specs/scorers.md).

A transparent lower anchor for the LLM and transformer scorers. Hawkish and dovish hits come from
the packaged lexicon ``cbtone/data/lexicon/hawkdove_v1.csv`` (unigrams and modifier+noun bigrams in
the style of Apel & Blix Grimaldi 2014, ``apel2014informative``; ECB-style weighted n-grams after
Picault & Renault 2017, ``picault2017words``; expectation terms after Bennani & Neuenkirch 2017,
``bennani2017home``; FOMC label concepts after Shah et al. 2023, ``shah2023trillion``).

Loughran & McDonald (2011, ``loughran2011liability``) is used only through
:class:`LMWordLists`: its Negative / Positive / Uncertainty lists are an *optional feature*
(:meth:`DictionaryScorer.lm_features`) and never change the index. The master dictionary is free
for academic research but carries no redistribution grant, so it is **not shipped**; it is
downloaded into ``data/cache/`` at run time (docs/sources/LICENSES.md).
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from cbtone.schema import Language
from cbtone.scorers.base import Scorer, ToneScore
from cbtone.sources.base import PoliteFetcher
from cbtone.text.split import split_sentences

SCORER_ID = "dict-v1"
LEXICON_NAME = "hawkdove_v1.csv"

#: A hit is flipped when one of these precedes it within ``NEGATION_WINDOW`` tokens.
NEGATORS = frozenset({"not", "no", "never", "without", "neither", "nor", "less"})
NEGATION_WINDOW = 5  # 3 missed "did not see a need to tighten" (checked before any corpus scoring)

#: Neutral mass is ``NEUTRAL_BASE + NEUTRAL_PER_SENTENCE * n_sentences`` (spec: ``1 + 0.5 * S``),
#: against weighted hawkish / dovish hit totals. One strong hit in a one-sentence text therefore
#: gives ``h / (h + n) = 1 / 2.5 = 0.4``; each extra sentence dilutes the evidence.
NEUTRAL_BASE = 1.0
NEUTRAL_PER_SENTENCE = 0.5

MAX_EVIDENCE = 10

#: Words that may sit *between* the tokens of a multi-word term (``lowered the policy rate``
#: matches ``lower rate``), at most ``MAX_GAP`` of them in a row.
FILLERS = frozenset(
    {"the", "a", "an", "its", "our", "their", "of", "in", "for", "policy", "interest", "key"}
    | {"benchmark", "target", "official"}
)
MAX_GAP = 2

_TOKEN = re.compile(r"[^\W_]+")

# --- Loughran-McDonald master dictionary (run-time download, not redistributed) -------------
LM_PAGE_URL = "https://sraf.nd.edu/loughranmcdonald-master-dictionary/"
# The "CSV Format" link on LM_PAGE_URL (Drive file id read from the page, 2026-10-14).
LM_CSV_URL = "https://drive.google.com/uc?export=download&id=1iq2RUf8qGFEAk1g8wQntP3habOnR3fXF"
LM_CACHE_FILE = "Loughran-McDonald_MasterDictionary.csv"
CACHE_DIR = Path("data/cache")


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens (letters and digits)."""
    return _TOKEN.findall(text.lower())


def stem(token: str) -> str:
    """Crude suffix stripper so ``raise/raised/raises/raising`` and ``rate/rates`` share a stem.

    It only has to be applied identically to lexicon terms and to text, not to be linguistically
    right. Irregular forms (``rose``, ``fell``) are listed explicitly in the lexicon.
    """
    t = token
    if len(t) > 4 and t.endswith("ies"):
        t = t[:-3] + "y"
    elif len(t) > 5 and t.endswith("ing"):
        t = _undouble(t[:-3])
    elif len(t) > 4 and t.endswith("ed"):
        t = _undouble(t[:-2])
    elif len(t) > 4 and t.endswith("es"):
        t = t[:-2]
    elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    if len(t) > 3 and t.endswith("e"):
        t = t[:-1]
    return t


def _undouble(t: str) -> str:
    return t[:-1] if len(t) > 2 and t[-1] == t[-2] and t[-1] not in "ls" else t


@dataclass(frozen=True)
class LexiconEntry:
    """One row of ``hawkdove_v1.csv``."""

    term: str
    polarity: str  # "hawkish" | "dovish"
    weight: float
    source_key: str  # key in docs/literature/refs.bib
    note: str

    @property
    def stems(self) -> tuple[str, ...]:
        return tuple(stem(t) for t in tokenize(self.term))


def load_lexicon(path: Path | str | None = None) -> list[LexiconEntry]:
    """Read the packaged lexicon (or ``path``); validates polarity, weight and uniqueness.

    Lexicon construction follows ``apel2014informative`` (modifier+noun bigrams) and
    ``picault2017words`` (weighted n-grams); per-row sources are in the ``source_key`` column.
    """
    if path is None:
        raw = (resources.files("cbtone") / "data" / "lexicon" / LEXICON_NAME).read_text("utf-8")
    else:
        raw = Path(path).read_text("utf-8")
    entries: list[LexiconEntry] = []
    seen: dict[tuple[str, ...], str] = {}
    for row in csv.DictReader(raw.splitlines()):
        entry = LexiconEntry(
            term=row["term"].strip().lower(),
            polarity=row["polarity"].strip(),
            weight=float(row["weight"]),
            source_key=row["source_key"].strip(),
            note=row["note"].strip(),
        )
        if entry.polarity not in ("hawkish", "dovish"):
            raise ValueError(f"bad polarity {entry.polarity!r} for term {entry.term!r}")
        if entry.weight <= 0 or not entry.stems:
            raise ValueError(f"bad weight or empty term: {entry.term!r}")
        if not entry.source_key:
            raise ValueError(f"term {entry.term!r} has no source_key")
        if seen.setdefault(entry.stems, entry.polarity) != entry.polarity:
            raise ValueError(f"term {entry.term!r} clashes with an opposite-polarity term")
        entries.append(entry)
    return entries


@dataclass(frozen=True)
class Hit:
    """A matched lexicon phrase. ``polarity`` is the effective one, after negation."""

    polarity: str
    weight: float
    span: str  # tokens from the negator (if any) to the end of the phrase
    negated: bool
    start: int
    end: int  # exclusive token index


@dataclass(frozen=True)
class LMWordLists:
    """Loughran & McDonald (2011, ``loughran2011liability``) Negative / Positive / Uncertainty."""

    negative: frozenset[str]
    positive: frozenset[str]
    uncertainty: frozenset[str]


def load_lm_wordlists(path: Path | str) -> LMWordLists:
    """Read the three lists from a Loughran-McDonald master dictionary CSV.

    Implements the list definitions of ``loughran2011liability``: a word is in a list when the
    column (``Negative`` / ``Positive`` / ``Uncertainty``) holds a non-zero year.
    """
    lists: dict[str, set[str]] = {"Negative": set(), "Positive": set(), "Uncertainty": set()}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = {"Word", *lists} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"not a Loughran-McDonald master dictionary: missing {sorted(missing)}"
            )
        for row in reader:
            for col, words in lists.items():
                if (row[col] or "0").strip() not in ("", "0"):
                    words.add(row["Word"].strip().lower())
    return LMWordLists(
        frozenset(lists["Negative"]), frozenset(lists["Positive"]), frozenset(lists["Uncertainty"])
    )


def fetch_lm_master_dictionary(
    fetcher: PoliteFetcher | None = None, cache_dir: Path = CACHE_DIR
) -> Path:
    """Download the master dictionary into ``cache_dir`` (git-ignored) and return its path.

    The dictionary (``loughran2011liability``) is free for academic research; commercial use needs
    a licence from its authors and there is no redistribution grant, so it is never committed or
    packaged. If the Drive link stops working, download the CSV by hand from ``LM_PAGE_URL`` and
    save it at ``cache_dir / LM_CACHE_FILE``.
    """
    target = cache_dir / LM_CACHE_FILE
    if target.exists():
        return target
    f = fetcher or PoliteFetcher(raw_dir=cache_dir)
    content = f.get("lm_dictionary", LM_CSV_URL).content
    head = content[:2000].decode("utf-8-sig", errors="replace")
    if not head.startswith("Word,") or "Negative" not in head:
        raise RuntimeError(
            f"{LM_CSV_URL} did not return the master dictionary CSV; download it manually "
            f"from {LM_PAGE_URL} to {target}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


class DictionaryScorer(Scorer):
    """Weighted hawkish/dovish phrase counts with negation (``apel2014informative``).

    ``h`` and ``d`` are the summed weights of hawkish and dovish hits; ``n = 1 + 0.5 * S`` where
    ``S`` is the sentence count; the result is ``ToneScore.from_probs(h, d, n)``. ``model_digest``
    is a hash of the lexicon file contents, so cached scores are tied to the exact word list.
    """

    scorer_id = SCORER_ID
    languages = frozenset({"en"})

    def __init__(
        self, lexicon: Iterable[LexiconEntry] | None = None, lm: LMWordLists | None = None
    ) -> None:
        self.entries = list(lexicon) if lexicon is not None else load_lexicon()
        self.lm = lm
        self._by_first: dict[str, list[LexiconEntry]] = {}
        for e in self.entries:
            self._by_first.setdefault(e.stems[0], []).append(e)
        for cands in self._by_first.values():  # longest phrase first, then heaviest
            cands.sort(key=lambda e: (-len(e.stems), -e.weight, e.term))
        canon = "\n".join(
            f"{e.term}|{e.polarity}|{e.weight}" for e in sorted(self.entries, key=lambda e: e.term)
        )
        self.model_digest = hashlib.sha256(canon.encode()).hexdigest()[:12]

    # -- matching ---------------------------------------------------------------------------
    def _phrase_end(
        self, tokens: list[str], stems: list[str], i: int, want: tuple[str, ...]
    ) -> int:
        """Exclusive end index if ``want`` matches from ``i`` (allowing filler gaps), else -1."""
        j = i
        for target in want[1:]:
            gap = 0
            j += 1
            while j < len(stems) and stems[j] != target and tokens[j] in FILLERS and gap < MAX_GAP:
                j += 1
                gap += 1
            if j >= len(stems) or stems[j] != target:
                return -1
        return j + 1

    def find_hits(self, sentence: str) -> list[Hit]:
        """Left-to-right, longest-match, non-overlapping hits in one sentence, negation applied."""
        tokens = tokenize(sentence)
        stems = [stem(t) for t in tokens]
        hits: list[Hit] = []
        i = 0
        while i < len(tokens):
            for e in self._by_first.get(stems[i], ()):
                end = self._phrase_end(tokens, stems, i, e.stems)
                if end < 0:
                    continue
                neg = next(
                    (k for k in range(max(0, i - NEGATION_WINDOW), i) if tokens[k] in NEGATORS),
                    None,
                )
                pol = e.polarity
                if neg is not None:
                    pol = "dovish" if pol == "hawkish" else "hawkish"
                span = " ".join(tokens[(i if neg is None else neg) : end])
                hits.append(Hit(pol, e.weight, span, neg is not None, i, end))
                i = end - 1
                break
            i += 1
        return hits

    # -- scoring ----------------------------------------------------------------------------
    def score_text(self, text: str, lang: Language = "en") -> ToneScore:
        """Score ``text`` as described in the class docstring (``apel2014informative``)."""
        if not self.supports(lang):
            raise ValueError(f"{self.scorer_id} reads {sorted(self.languages)} only, not {lang!r}")
        sentences = split_sentences(text, "en") if text.strip() else []
        hits = [h for s in sentences for h in self.find_hits(s)]
        h_w = sum(h.weight for h in hits if h.polarity == "hawkish")
        d_w = sum(h.weight for h in hits if h.polarity == "dovish")
        n_w = NEUTRAL_BASE + NEUTRAL_PER_SENTENCE * len(sentences)
        return ToneScore.from_probs(
            h_w,
            d_w,
            n_w,
            scorer_id=self.scorer_id,
            evidence_spans=[h.span for h in hits[:MAX_EVIDENCE]],
            model_digest=self.model_digest,
        )

    def lm_features(self, text: str) -> dict[str, int]:
        """Counts of Loughran-McDonald Negative / Positive / Uncertainty tokens (optional feature).

        Uses the lists of ``loughran2011liability``; they never enter the index. Needs ``lm``.
        """
        if self.lm is None:
            raise RuntimeError("no Loughran-McDonald lists loaded; pass lm=load_lm_wordlists(...)")
        toks = tokenize(text)
        return {
            "tokens": len(toks),
            "negative": sum(t in self.lm.negative for t in toks),
            "positive": sum(t in self.lm.positive for t in toks),
            "uncertainty": sum(t in self.lm.uncertainty for t in toks),
        }
