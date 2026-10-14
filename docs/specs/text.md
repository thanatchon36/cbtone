# Spec: text utilities (`src/cbtone/text/`) and corpus snapshot (`src/cbtone/sources/snapshot.py`)

Read: MISSION.md §1.1 + §3 (`cbtone.text`), `src/cbtone/schema.py`.

1. `cbtone/text/split.py`: `split_sentences(text, lang) -> list[str]` for en/id/ms (pysbd if it
   supports them, otherwise a regex splitter with an abbreviation list: "U.S.", "Mr.", "Dr.", "No.",
   "e.g.", "i.e.", "Jan." …, decimals "2.5", "Rp.", "Bhd.", "S$"), zh (split on 。！？； and
   newline, keep quotes attached), th (`pythainlp.tokenize.sent_tokenize`, put in an optional extra
   `[thai]` and import lazily; fallback: split on whitespace runs/newlines with a warning).
   `split_paragraphs(text)`. Tests with tricky cases for each language.
2. `cbtone/text/clean.py`: `normalize(text)` — Unicode NFKC, unify quotes/dashes, collapse
   whitespace, strip zero-width chars, de-hyphenate PDF line breaks ("infla-\ntion" → "inflation").
3. `cbtone/text/langdetect.py`: a tiny script-based + stopword-based detector for {en,id,ms,zh,th}
   (no heavy dep). Note id vs ms are close; use distinctive stopwords ("tidak"/"bagi"/"kerana"/
   "dasar" vs "yang"/"untuk"/"karena"/"kebijakan"). Tests.
4. `cbtone/text/mask.py`: `mask_entities(text, lang="en") -> str` replacing bank names (all banks in
   `Bank` + common variants: "Federal Reserve", "the Fed", "FOMC", "Committee"? — NO, keep generic
   "Committee"), country/region/currency names ("Singapore", "euro area", "rupiah", "ringgit", "S$NEER"
   → "[CURRENCY] NEER"), dates (months, years, quarters, "2024Q1"), and numeric rate levels
   ("5.25 percent", "25 basis points", "4¾%", "1/4 percentage point") with placeholders
   [BANK], [COUNTRY], [CURRENCY], [DATE], [RATE], [BP]. Must not mask words like "inflation",
   "growth". Tests incl. idempotence (mask(mask(x)) == mask(x)).
5. `cbtone/sources/snapshot.py`: `build_snapshot(documents: Iterable[Document], out_dir)` writes
   `documents.parquet` (one row per Document; sections as list[struct]), `sentences.parquet`
   (doc_id, para_idx, sent_idx, text, lang), `manifest.parquet` (doc_id, bank, date, doc_type,
   language, url, sha256, fetched_at, n_chars, n_sentences, redistributable: bool) and
   `VERSION` (date + sha256 over the sorted manifest). A `redistributable` flag per bank comes from a
   dict argument; when False the text columns are replaced by null in the committed parquet and a
   full-text copy goes to `data/corpus/private/` (git-ignored). Deterministic row order.
Tests offline; ruff + mypy --strict clean. Only create files under src/cbtone/text/,
src/cbtone/sources/snapshot.py and tests/. pysbd, yfinance and the `[thai]` extra (pythainlp) are already installed; do NOT run `uv add` (parallel agents share pyproject.toml) — list any other dep you need in your report.
Don't commit; report ≤ 250 words.
