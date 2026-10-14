Finding 8: what it costs to run this on your own hardware.

Everything used a 4-billion-parameter open model through Ollama. No API, no per-token fees, no text leaving the machine.

- Desktop RTX 4070 Ti (12 GB): about 0.5 s per decision statement. Every LLM run in the study, including the stability tests, took about 2 hours.
- MacBook Air M4 (16 GB): about 3.5 s per statement with text capped at 3,000 characters.
- Fine-tuning a small multilingual model on the laptop: 6 minutes.

Scores are cached by content hash, so re-running the whole analysis makes no new model calls.

Cheap enough to monitor every new statement. Given the other findings, treat the output as a descriptive series, not a forecast.

https://github.com/thanatchon36/cbtone
