# Executive summary: LLM tone scores of central-bank text

*One page for a CIO or head of macro research. Independent open-source project; not investment advice.
Full paper: `paper/paper.pdf`. Every number below comes from `results/summary.json`.*

## The question

Can a small language model running on your own hardware (`qwen3:4b`, no cloud API) turn central-bank decision
statements into a hawkish/dovish score that is worth something: predicting the next decision, explaining the market
move on the day, and working the same way in Indonesian and Malay as in English? We pre-registered thresholds before
scoring anything and tested seven banks: Fed, ECB, BoE, RBA, MAS, Bank Indonesia and Bank Negara Malaysia.

## What we found

| Use | Verdict | The number |
|---|---|---|
| Predict the next rate decision (vs "same as last time") | **No** | 0 of 4 testable banks. ECB came closest (log-loss gain +0.058, CI above zero) but failed the multiple-testing correction. |
| Explain the FX / 2-year-yield move on release | **No, with one exception** | 1 of 11 bank–market pairs: RBA 2Y, +9 bp per unit of tone surprise, R² 0.10. Pooled FX effect ≈ 0. |
| Beat a simple word-list dictionary | **Rarely** | Better on human-labelled Fed sentences (macro-F1 0.48 vs 0.27); no better on any market or decision test after correction. |
| Same score for the Indonesian/Malay and English versions | **Partly** | Direction agrees (stance flips in about 2 % of pairs), strength does not (ρ 0.61 BI, 0.53 BNM, against a 0.70 bar). |
| Stable when you reword the prompt | **No** | Agreement across five equivalent prompts α 0.65 (documents), 0.42 (sentences), against a 0.667 bar. Changing the model version moves scores even more. |
| Robust to training-data contamination | **Nothing to protect** | No finding survived; masking names and dates did not change the (null) picture. |

## Where it is unreliable

- **Prompt and model version.** The same statement gets a materially different score under a reworded prompt or a
  different small model. A tone series is only comparable over time if both are frozen and logged.
- **Southeast Asia.** Too little history for strong tests: BI text starts in 2016, BNM rarely changes rates, MAS
  sets an exchange-rate band. Several cells were underpowered by the pre-registered rules and are reported, not tested.
- **Persistence is hard to beat.** Most of what can be predicted about the next decision is in the last decision.

## What it costs to run locally

| Hardware | Per decision document | Full study (≈ 1,400 docs + checks) |
|---|---|---|
| Desktop RTX 4070 Ti (12 GB) | ≈ 0.5 s | ≈ 2 h for every LLM run, including stability tests |
| MacBook Air M4 (16 GB) | ≈ 3.5 s (text capped at 3,000 chars) | needs the pre-registered reduced plan |

Scoring a new statement takes seconds on either machine; there are no per-token fees, and no text leaves the machine.
Fine-tuning the small multilingual model took 6 minutes on the laptop.

## Bottom line

Run locally, a small LLM gives a **descriptive** tone series that tracks the broad policy cycle and reads Fed
sentences better than a dictionary. We found **no reliable trading or forecasting signal** in it at seven banks once
persistence, placebos, multiple testing and contamination checks are applied. Treat it as a monitoring aid with
documented prompt and model versions, not as an alpha source.
