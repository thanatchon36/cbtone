# Contributing to cbtone

Thanks for helping. This project is research software with a pre-registered study, so a few rules
are stricter than usual. Please also read [DISCLAIMER.md](DISCLAIMER.md): contributions must use
**public documents only** and must not add commentary on any bank's policy choices.

## Development workflow

```bash
uv sync                      # core environment (no extras)
make test                    # pytest with coverage; network tests are deselected by default
make lint                    # ruff check, ruff format --check, mypy --strict on src/cbtone
make format                  # auto-format
make quick-ci                # dictionary scorer on the committed mini corpus, no network
make docs                    # build the documentation site (needs the [docs] extra)
```

- Run `make test lint` before opening a pull request. CI runs the same on Python 3.11 and 3.13.
- Tests must work **offline**. Use trimmed real pages as fixtures under `tests/fixtures/<bank>/`.
  A test that needs the internet must carry `@pytest.mark.network`.
- Type hints throughout; `mypy --strict` must stay clean for `src/cbtone`.
- Do not run long jobs (full-corpus LLM scoring) as part of a contribution.

### Pre-registration rules

The study is pre-registered in [`docs/RESEARCH_QUESTIONS.md`](docs/RESEARCH_QUESTIONS.md)
(tag `prereg-v1`). Therefore:

- Do not change hypotheses, metrics, thresholds, the primary-document table or the power rules in
  that file after scoring has started. If a change is unavoidable, add a dated amendment and say
  why in `docs/DECISIONS.md`; never rewrite history.
- Results that contradict the pre-registration are reported as refuted, not re-framed.
- New analyses that were not pre-registered are labelled exploratory.
- Every LLM result needs a masked-text variant and a post-cutoff split.
- A headline metric exactly at 0, 1 or 100 %, a correlation above 0.95, or a result more than 2x
  away from the literature's typical range fails the build until explained in
  [`docs/ANOMALIES.md`](docs/ANOMALIES.md).

### Recording decisions

Add every design decision to [`docs/DECISIONS.md`](docs/DECISIONS.md) as the next `D<n>` entry:
**what** you chose, **why**, and **alternatives rejected**, with the date. Data surprises go to
`docs/ANOMALIES.md`. Do not edit earlier entries except to add a dated note.

## Add a central bank adapter

An adapter turns one bank's public pages into `Document` objects. The interface is
`SourceAdapter` in `src/cbtone/sources/base.py`:

- `list_urls(start_year, end_year)` yields `(url, hints)`; `hints` carries at least `doc_type` and
  `date` (ISO decision or meeting date) and normally `language`.
- `parse(raw, hints)` is **pure** (no network): it turns one `RawResponse` into `Document`s.
- All HTTP goes through `self.fetcher` (a `PoliteFetcher`); `fetch()` is already provided.

### Politeness rules (not negotiable)

- Use only `self.fetcher.get(self.bank, url)` (or `.post`). Never call `httpx` or `requests`
  directly: that would skip robots.txt, the rate limit and the cache.
- `PoliteFetcher` honours `robots.txt`, waits at least 2 s per host (longer if `Crawl-delay`
  says so), sends a descriptive User-Agent and caches every response under `data/raw/<bank>/`
  with its SHA-256. Do not lower `min_interval_s` for live runs.
- If the site blocks automated access (`BlockedError`, HTTP 401/403/429, or a block page), stop
  for that bank. Do not rotate user agents or otherwise get around the block. Write the exact
  URLs a human can download to `docs/sources/NEEDED.md`, and make `parse` work on those manual
  files (`cbtone parse <bank> --file ...` helps you debug).
- While developing, fetch a handful of pages, not the whole history.

### The walkthrough: about 30 lines

Step 1. Add the bank code to the `Bank` literal in `src/cbtone/schema.py` and create
`src/cbtone/sources/<bank>.py` (the registry finds the class whose `bank` attribute matches):

```python
"""Example bank adapter (illustrative). Terms: https://example.org/terms (record the quote)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from bs4 import BeautifulSoup

from cbtone.schema import Document, Section
from cbtone.sources.base import RawResponse, SourceAdapter

BASE = "https://www.example.org"


class XyzAdapter(SourceAdapter):
    bank = "xyz"  # must be a member of cbtone.schema.Bank

    def list_urls(self, start_year: int, end_year: int) -> Iterator[tuple[str, dict[str, str]]]:
        for year in range(start_year, end_year + 1):
            index = self.fetcher.get(self.bank, f"{BASE}/mpc/{year}/")  # robots, rate limit, cache
            for a in BeautifulSoup(index.content, "lxml").select("ul.releases a"):
                d = date.fromisoformat(a["data-date"])  # decision date, not release date
                yield f"{BASE}{a['href']}", {"doc_type": "statement", "date": d.isoformat()}

    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        soup = BeautifulSoup(raw.content, "lxml")  # pure: no network here
        paras = [p.get_text(" ", strip=True) for p in soup.select("article p")]
        sections = [Section(text=t) for t in paras if t]
        return [
            Document(
                bank=self.bank,
                date=date.fromisoformat(hints["date"]),
                doc_type="statement",
                language="en",
                title=soup.title.get_text(strip=True) if soup.title else "",
                text="\n\n".join(s.text for s in sections),
                sections=sections,
                url=raw.url,
                sha256=raw.sha256,
                fetched_at=raw.fetched_at,
            )
        ]
```

Step 2. Fill the module docstring like the existing adapters (see `src/cbtone/sources/rba.py`):
document types, index and document URL patterns, date range, languages, the release-time rule
with its source (`published_at_utc` stays `None` when no time is documented), and a **quote of
the bank's terms of use** with the URL.

Step 3. Register the bank:

- `src/cbtone/sources/registry.py`: add it to `REDISTRIBUTABLE` (`False` unless the terms clearly
  allow redistributing the text; unlisted banks are withheld).
- `src/cbtone/corpus.py`: add it to `PRIMARY` (primary document type and language). Whether it
  joins `HEADLINE` is a pre-registration question: raise it in the pull request.
- `src/cbtone/events/engine.py`: add its FX and 2-year series to `BANK_SERIES` if market data exist.

Step 4. Tests, offline, with fixtures. Save a few trimmed real pages (one per document type and
layout era) under `tests/fixtures/<bank>/` and write `tests/test_source_<bank>.py` following
`tests/test_source_rba.py`: build a `RawResponse` from the fixture file, call `parse`, and assert
text content, section count, no navigation or footer boilerplate, `doc_id`, and release time.
Test `list_urls` with a `PoliteFetcher(raw_dir=tmp_path, offline=True)` pre-filled cache or a
`httpx.MockTransport`, so nothing touches the network.

Step 5. Document the source in `docs/sources/<bank>.md`: what was fetched, URL patterns, quirks,
the cross-check against the bank's published meeting schedule, and known gaps. Add the bank to the
table in `docs/site/adapters.md`.

Step 6. Add a row to the per-bank table in
[`docs/sources/LICENSES.md`](docs/sources/LICENSES.md): the terms, whether the text may be
redistributed, and what is committed (text, or URL + SHA-256 only).

Step 7. Run `make test lint`, then add a `D<n>` entry in `docs/DECISIONS.md` for any non-obvious
choice (for example how decision dates are defined).

## Add a scorer

The contract is in `src/cbtone/scorers/base.py`.

- Subclass `Scorer`. Set `scorer_id` and `languages` (a `frozenset` of language codes; default
  `{"en"}`), and implement `score_text(text, lang) -> ToneScore`. `score_sentences` and
  `score_document` come for free. `score_document` reads the pre-registered policy text
  (`cbtone.text.paragraphs.policy_text`, capped at `DOC_CHAR_CAP` characters) so that all
  scorers read the same input.
- Return a `ToneScore`: `hawkish_p`, `dovish_p`, `neutral_p` (each in [0, 1], summing to 1) and
  `index = hawkish_p - dovish_p`. The model validator rejects inconsistent values. Use
  `ToneScore.from_probs(h, d, n, scorer_id=...)` to normalise raw weights. Fill `model_digest` and
  `prompt_id` whenever the scorer has them, and `evidence_spans` if it quotes text.
- Scorers that are slow or non-deterministic should cache through `ScoreCache` (key = scorer id,
  model digest, prompt id, variant, text) so long runs are resumable.
- Heavy imports must be lazy so that `pip install cbtone` stays light; declare new dependencies in
  an extra, never in the core list.
- Register it in `src/cbtone/scorers/__init__.py` (`SCORERS` and `get_scorer`), add
  `tests/test_scorer_<name>.py` that runs without network or GPU (stub the model), and document it
  in `docs/site/scorers.md`.
- A new scorer used in the study needs a pre-registration amendment first.

## Add a language

Languages are a closed `Literal` (`Language` in `src/cbtone/schema.py`). To add one:

1. Extend `Language` and, if automatic detection should know it, `src/cbtone/text/langdetect.py`.
2. **Sentence splitter:** `split_sentences` in `src/cbtone/text/split.py` has Latin, Chinese and
   Thai branches. Add a branch (or confirm the Latin one is adequate, with tests on real text).
3. **Entity mask:** `src/cbtone/text/mask.py` replaces bank names, country names, currencies,
   dates and rate levels with placeholders for the masked-text LLM variant. Add the language's
   month names, units and bank and country names, with tests in `tests/test_text_mask.py`.
4. **Paragraph cues:** `_CUES` in `src/cbtone/text/paragraphs.py` maps a language to regex cues for
   the decision, forward-guidance, outlook and risks paragraphs. Add a block for the language and
   test it on fixtures.
5. Check that each scorer either supports the language (`languages`) or is skipped for it.
6. Record the choices in `docs/DECISIONS.md`.

## Add a market series

`src/cbtone/markets/registry.py` holds `REGISTRY`: one `SeriesSpec` per daily series with its
kind (`fx` or `yield`), the IANA time zone and local time of its daily close, the source and a
description. The close time decides which close is the first to reflect a release, so cite where
the convention comes from in `docs/sources/markets.md`.

1. Add the `SeriesSpec` (for Yahoo FX tickers, add the ticker to `FX_TICKERS`; yields use `_yld`).
2. Implement the download in `src/cbtone/markets/fx.py` or `yields.py` if the source is new.
   Only public data; respect the source's terms and rate limits. Market data are not committed
   when the source's terms forbid it.
3. Map banks to the series in `BANK_SERIES` and give the sign convention in `SERIES_SIGN`
   (`src/cbtone/events/engine.py`).
4. Add tests in `tests/test_markets.py` / `tests/test_markets_clean.py` with a small fixture, and
   record any bad-tick filtering in `docs/ANOMALIES.md`.

## Pull requests

Keep changes small and focused, explain the why, and mention which decisions you added. Do not
commit raw caches, model weights or any text from a source whose terms forbid redistribution.
