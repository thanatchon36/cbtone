# Cookbook

## Add a central bank in 30 lines

An adapter implements two methods of `SourceAdapter`: `list_urls` (which pages exist) and `parse`
(one raw page to `Document`s, no network). Everything else, including `fetch`, is inherited.
All requests go through `self.fetcher`, a `PoliteFetcher`, which applies robots.txt, the 2 s rate
limit and the on-disk cache for you. Never call `httpx` directly.

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

Then, in order: add the code to `Bank` in `src/cbtone/schema.py`; register it in
`sources/registry.py` (`REDISTRIBUTABLE`), `corpus.py` (`PRIMARY`) and `events/engine.py`
(`BANK_SERIES`); save trimmed real pages as fixtures and write an offline test modelled on
`tests/test_source_rba.py`; write `docs/sources/<bank>.md`; and add a row to
`docs/sources/LICENSES.md`. Debug a saved page with:

```bash
cbtone parse xyz --file page.html --url https://www.example.org/mpc/2026/1 --hint date=2026-01-28 --hint doc_type=statement
```

The full checklist, including politeness rules, is in
[CONTRIBUTING.md](https://github.com/thanatchon36/cbtone/blob/main/CONTRIBUTING.md#add-a-central-bank-adapter).

## Score your own text

From Python, with the dictionary scorer (core install, no network):

```python
from cbtone.scorers import get_scorer

scorer = get_scorer("dict")
score = scorer.score_text(
    "The Committee decided to raise the target range and expects further tightening.",
    "en",
)
print(score.index, score.label)   # index = hawkish_p - dovish_p, in [-1, 1]
```

For a whole `Document`, call `scorer.score_document(doc)`, which scores the pre-registered policy
text. `get_scorer("llm", model="qwen3:4b")` gives the local-LLM scorer (Ollama must be running);
add `masked=True` for the masked-text variant.

To score the committed Fed and RBA fixture corpus from the command line:

```bash
cbtone score --scorer dict fed rba --corpus tests/fixtures/corpus_mini --out /tmp/quick.parquet
```

To score your own corpus, write `Document` objects and build a snapshot:

```python
from cbtone.sources.snapshot import build_snapshot

build_snapshot(my_documents, "my_corpus", {"fed": True})   # only mark banks you may redistribute
```

then `cbtone score --scorer dict fed --corpus my_corpus`. Documents of banks not in the
`redistributable` map are withheld (text written to a git-ignored `private/` folder) unless you pass
`default_redistributable=True`.

## Run an event study

```bash
cbtone fetch fed rba                                  # polite download (cached)
cbtone snapshot fed rba --out my_corpus               # build a snapshot from the cache, no network
cbtone markets                                        # daily FX and 2y/10y yields (not committed)
cbtone score --scorer dict fed rba --corpus my_corpus
cbtone events fed rba --corpus my_corpus              # event timestamps + signed [t-1, t+1] moves
```

Use `--out` / `--corpus` as shown so that you do not overwrite the default `data/corpus`
snapshot. `cbtone decisions` (policy-decision table) is only needed for the policy-signal tests, not
for `events`.

`results/events.parquet` then holds one row per primary document with its event timestamp, its
`timing` flag (`exact` or `day`) and the signed moves `move_fx` and `move_y2`. The regression of
moves on tone surprise, the Newey-West errors and the placebos are in `cbtone.events.engine` and
`cbtone.analysis`; the pre-registered use is described in
[RESEARCH_QUESTIONS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/RESEARCH_QUESTIONS.md) (RQ2). Read
[Concepts](concepts.md#events) first for how the timestamp and window are defined.
