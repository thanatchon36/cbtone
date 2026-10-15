# Scorers

All scorers implement `cbtone.scorers.Scorer` and return `ToneScore` (see
[Concepts](concepts.md#tonescore)). Build one with `cbtone.scorers.get_scorer(name, **kw)`; heavy
dependencies are imported lazily.

| `--scorer` | Family | Needs | Languages | Notes |
|---|---|---|---|---|
| `dict` | Dictionary | core install | en | Phrase lexicon `hawkdove_v1.csv` shipped in the package, with a crude stemmer and negation handling. Written for cbtone following published construction principles; not a replication of any published list. Optional Loughran-McDonald features are downloaded at run time, never shipped. |
| `fomc-roberta` | Finance-tuned transformer | `[transformers]`; Hugging Face access to the gated model | en | `gtfintechlab/FOMC-RoBERTa`, revision pinned; CC-BY-NC-4.0, so non-commercial. Training data came from FOMC text, which matters for transfer to other banks. The paper uses a replication (`fomc-roberta-repl`) because access to the gated model was never granted: rebuild it with `make fomc-roberta`, or download it from [`thanatchon36/cbtone-fomc-roberta-repl`](https://huggingface.co/thanatchon36/cbtone-fomc-roberta-repl) (CC-BY-NC-4.0), then load it with `--scorer ft --model-dir <dir>`. |
| `llm` | Local LLM | a running Ollama and the model pulled | en, id, ms, th, zh | Default `qwen3:4b`, temperature 0, five prompt variants P1 to P5, optional `--masked` input and `--evidence` quotes. Calls are cached by content hash and resumable; the model tag and digest are recorded. |
| `ft` | Fine-tuned small model | `[finetune]` (training) or `[transformers]` (inference); `--model-dir` | the languages it was trained on | XLM-RoBERTa-base fine-tuned on LLM silver labels. It refuses training rows that come from non-commercial evaluation-only data. |

The `[api]` extra is reserved for an optional hosted-API scorer; no such scorer is shipped yet, and none is ever required to reproduce results.

## Contamination

A language model may have seen central-bank texts and the outcomes that followed. For that reason
every LLM result is reported with:

- a **masked** variant (`--masked`): bank names, dates, numeric rate levels, currencies and
  country names replaced by placeholders;
- a **post-cutoff** split: documents dated after the model's documented training cutoff (or its
  public release date when none is documented).

A claim of predictive signal is made only where it survives both.

## Choosing a scorer

There is no default winner: the pre-registered questions compare them. Read
[RESEARCH_QUESTIONS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/RESEARCH_QUESTIONS.md) for what is tested, and
[DECISIONS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/DECISIONS.md) for the model and prompt choices.

To write your own, see [CONTRIBUTING.md](https://github.com/thanatchon36/cbtone/blob/main/CONTRIBUTING.md#add-a-scorer).
