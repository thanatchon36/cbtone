# Concepts

## Document

Every adapter produces the same pydantic model (`cbtone.schema.Document`):

| Field | Meaning |
|---|---|
| `bank` | bank code (`fed`, `ecb`, `boe`, `rba`, `mas`, `bi`, `bnm`, `bot`, `pboc`) |
| `date` | the **decision or meeting date** the document belongs to (not necessarily the release date) |
| `published_at_utc` | release instant, only when the bank documents it; otherwise `None` |
| `doc_type` | `statement`, `minutes`, `press_conference`, `mps`, `communique`, `other` |
| `language` | `en`, `id`, `ms`, `zh`, `th` |
| `parallel_id` | shared by translations of the same document |
| `title`, `text`, `sections` | cleaned text, and the same text as paragraph-level `Section`s (with optional headings) |
| `url`, `sha256`, `fetched_at` | provenance: public URL, hash of the raw bytes, fetch time |

`doc_id` is `bank:date:doc_type:language`, for example `fed:2026-01-28:statement:en`.
The corpus snapshot is three parquet tables (`documents`, `sentences`, `manifest`) plus a
`VERSION` file whose value includes a hash of the manifest. Where a source's terms forbid
redistribution, the committed `text` columns are null and the full text is rebuilt locally from
the fetch cache.

## ToneScore

Every scorer returns a `cbtone.scorers.ToneScore`:

- `hawkish_p`, `dovish_p`, `neutral_p`: probabilities that sum to 1;
- `index = hawkish_p - dovish_p`, in [-1, 1];
- `label`: the argmax class (ties resolve to neutral);
- `scorer_id`, plus `model_digest` and `prompt_id` when the scorer has them, so a result can be
  traced to an exact model and prompt;
- `evidence_spans`: optional quotes from the text (LLM scorer with `--evidence`).

Document scores are computed on the **pre-registered policy text**: paragraphs tagged
`decision`, `forward_guidance`, `outlook` or `risks`, capped at a character budget (3,000 by default
in the CLI after budget-ladder decision D18; the pre-registered original was 6,000). All scorers read the
same input so they can be compared fairly.

## The decision table

`decisions.parquet` (built by `cbtone decisions`) has one row per policy decision or scheduled
meeting outcome, so tone can be tested against what happened next.

| Column | Meaning |
|---|---|
| `bank`, `date` | bank and announcement/meeting date |
| `direction` | `hike`, `hold` or `cut` |
| `magnitude_bp` | signed change in basis points (0 for a hold) |
| `rate_after`, `policy_instrument` | policy rate after the decision and which rate it is |
| `next_direction`, `next_date` | the following decision, the target of the RQ1 prediction tests |
| `source` | `bis`, `bank`, `mas_table` or `mas_text` |
| `unscheduled`, `effective_date` | out-of-meeting changes and the date the new rate shows in the series |

Rates and meeting dates come from public sources (BIS policy-rate series and meeting calendars).
MAS rows come from MAS's own decision table.

## Events

An **event** is a document release with a timestamp. `cbtone events` computes it as follows.

1. If `published_at_utc` is set, that instant is the event time (`timing = exact`).
2. Otherwise the event time is 00:00 local time on the release date (`timing = day`), so the
   window is wider (more noise) but never looks ahead.
3. The event day *t* is the first daily close strictly after the event time. The market move is
   the change from the close at *t*-1 to the close at *t*+1, signed so that positive means
   hawkish-consistent (domestic-currency appreciation, higher yields).

The regression of market moves on **tone surprise** (tone minus its AR(1) forecast fitted on prior
documents only) uses Newey-West standard errors with lag 1, and is always reported next to
placebos (shuffled-date tone, permuted labels, non-announcement days). Market data are fetched
with `cbtone markets` and are not committed.

## The pre-registration workflow

1. **Before scoring**: hypotheses, metrics, decision thresholds, power rules and the budget
   ladder are written in [RESEARCH_QUESTIONS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/RESEARCH_QUESTIONS.md)
   and tagged `prereg-v1`.
2. **Amendments** are dated entries in [DECISIONS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/DECISIONS.md) (what, why,
   alternatives rejected). Nothing is silently changed.
3. **Contamination checks** accompany every LLM result: a masked-text variant (bank names, dates,
   rate levels and country names replaced with placeholders) and a post-training-cutoff split.
4. **Sanity rules**: a headline metric exactly at 0, 1 or 100 %, a correlation above 0.95, or a
   value more than 2x outside the literature's range fails the build until explained in
   [ANOMALIES.md](https://github.com/thanatchon36/cbtone/blob/main/docs/ANOMALIES.md).
5. **Underpowered cells** are reported separately and excluded from multiple-comparison families
   and majority rules. A research question with too few powered banks is reported as untestable.
6. **Contradicting results** are reported as refuted, not re-framed.
