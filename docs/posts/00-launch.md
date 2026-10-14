I spent the last weeks testing a simple question: can a small language model running on my own machine read central-bank statements and find policy signal in them?

I wrote down the tests and thresholds first (git tag prereg-v1), then built a corpus of ~2,900 public documents from 7 central banks (Fed, ECB, BoE, RBA, MAS, Bank Indonesia, Bank Negara Malaysia) in English, Indonesian and Malay, and scored every decision statement with qwen3:4b via Ollama.

The short answer: no reliable signal. Every testable hypothesis was refuted at its pre-registered threshold. I report that as the result, not as a failure.

What is released:
- cbtone, an open-source Python library (Apache-2.0): polite fetchers, a versioned corpus, four scorer families, event studies
- masked-text and post-cutoff checks for training-data contamination
- a paper and every number regenerable with one command

Over the next posts I'll share one finding at a time.

Independent project; public documents only; not investment advice and no comment on any bank's policy.

https://github.com/thanatchon36/cbtone
