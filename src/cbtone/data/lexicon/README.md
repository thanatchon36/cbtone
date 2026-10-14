# hawkdove_v1.csv

Hawkish / dovish phrase lexicon for `cbtone.scorers.dictionary.DictionaryScorer` (`scorer_id="dict-v1"`).

Columns: `term, polarity (hawkish|dovish), weight, source_key, note`.

- `weight` is 1.0 for a strong, unambiguous phrase and 0.5 for a weaker or more ambiguous one.
- `source_key` is a key in `docs/literature/refs.bib`. It names the paper whose construction or concept the
  row instantiates:
  - `apel2014informative` (Apel & Blix Grimaldi 2014): modifier + noun bigrams (higher/rising/strong/weak +
    inflation/growth/demand/wages/...).
  - `picault2017words` (Picault & Renault 2017): ECB-style policy-action and forward-guidance n-grams.
  - `bennani2017home` (Bennani & Neuenkirch 2017): inflation and growth expectation terms.
  - `shah2023trillion` (Shah, Paturi & Chava 2023): the FOMC hawkish/dovish annotation concepts (target range,
    balance sheet).
- Matching: lower-case tokens, a crude suffix stemmer (`cbtone.scorers.dictionary.stem`), longest match first,
  up to two filler words (`the`, `policy`, `interest`, ...) allowed between the tokens of a phrase, and
  negation per the scorer docstring.

## Provenance (read this before citing the lexicon)

The terms were **written for cbtone** following the construction principles of the cited papers. They are not
copies of the original word lists, which were not consulted; `source_key` records the idea each row follows,
not that the exact term appears in the paper. Because of that, `dict-v1` must not be described as a
replication of Apel & Blix Grimaldi or Picault & Renault.

The Loughran & McDonald (2011, `loughran2011liability`) dictionary is not part of this file and is not shipped
(see `docs/sources/LICENSES.md`). Its Negative / Positive / Uncertainty lists are an optional run-time feature
only (`DictionaryScorer.lm_features`). The scorer's negators (`not, no, never, without, neither, nor, less`)
are a fixed list set by the spec, not taken from that dictionary.

Changing this file changes `DictionaryScorer.model_digest`, so cached scores are invalidated.
