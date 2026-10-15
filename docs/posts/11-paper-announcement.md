I asked a small language model to read 2,900 central-bank documents and tell me whether each one was hawkish or dovish. Then I asked whether that number predicted anything. I wrote down the tests before looking.

The setup: seven central banks (Fed, ECB, Bank of England, RBA, MAS, Bank Indonesia, Bank Negara Malaysia), three languages (English, Indonesian, Malay), one 4-billion-parameter open-weight model (qwen3:4b) on a consumer GPU. Hypotheses, thresholds, minimum sample sizes and the multiple-testing families were frozen in a public git tag before any scoring.

What the data said:

• Next rate decision. LLM tone beat "same as last time" at 0 of the 4 banks with enough data. The nearest miss was the ECB, and it did not survive the multiple-testing correction.
• Market reaction on announcement day. 1 of 11 bank–market pairs cleared a placebo (the Australian 2-year yield, about 9 bp per unit of tone surprise). The LLM never beat a word-list dictionary after correction.
• Same statement, two languages. Indonesian and English versions agree on direction 98 % of the time, but on strength only moderately (ρ = 0.61 and 0.53, against a bar of 0.70).
• Reword the prompt five ways. Agreement across paraphrases α = 0.65, below the 0.667 bar. Change the model version: α = 0.46.
• Human-labelled FOMC sentences. LLM 0.48 macro-F1, dictionary 0.27.

Then I retrained the published supervised model (FOMC-RoBERTa, which is gated, so I rebuilt it from the paper's recipe). It scores 0.71 on the same human labels, about 50 % better than the LLM. And it predicts the next decision exactly as badly: 0 of 4 banks, the Fed included, whose statements it was trained on. Its market-reaction R² is indistinguishable from the LLM's in all 11 cells.

That is the finding I did not expect. The limit is not how well the model reads the text. It is how little a single hawkish/dovish number can say about a decision that is mostly determined by the previous one.

Masking every bank name, date and rate level before scoring moved the estimates by almost nothing: there was no memorised signal to remove.

What a local LLM is good for, on this evidence: reading sentences better than a word list, in seconds, with no text leaving the machine. A monitoring aid. Not a forecasting signal.

Everything is open:
📄 Paper (every number generated from the results file): https://thanatchon36.github.io/cbtone/paper/
💻 Code and corpus pipeline, Apache-2.0: https://github.com/thanatchon36/cbtone — pip install cbtone
🤗 Models and the silver-label dataset: https://huggingface.co/thanatchon36
🔖 Pre-registration: git tag prereg-v1. Every deviation is logged with its date.

If you build or buy tone indices for central-bank text, I would like to hear where this is wrong.

Independent project; public documents only; not investment advice and no comment on any bank's policy.

#CentralBanking #MonetaryPolicy #NLP #LLM #OpenScience #Preregistration

Image: docs/posts/card.png
