Update: I retrained FOMC-RoBERTa myself, and it closes the last open cell in the study.

The reference model for my human-label test is FOMC-RoBERTa (Shah, Paturi & Chava 2023). It's gated on Hugging Face, and access never came through. So I rebuilt it from the paper's recipe: RoBERTa-large fine-tuned on the train split of their FOMC hawkish/dovish data, three seeds, with the final model picked on a validation split so the test set played no part.

On the 496-sentence FOMC test set (macro-F1):

- my replication: 0.71 (published: 0.72)
- local LLM (qwen3:4b): 0.48
- my word-list dictionary: 0.27

So a 355M-parameter model trained on ~1,600 labelled Fed sentences still beats a zero-shot 4B LLM by a wide margin on Fed text.

Does the better reader find the policy signal the LLM missed? No. It predicts the next rate decision no better than "same as last time" at any of the four banks with enough data, the Fed included, and it explains the market's reaction to statements no better than the LLM does. The limit isn't the model reading the text; it's how little a single hawkish/dovish number carries.

Outside the Fed it slips: on Singapore (MAS) sentences it drops 0.25. Those labels come from the LLM, though, so part of that drop is label noise. The dictionary doesn't drop at all. My pre-registered transfer hypothesis needed both to drop, so it could not have been supported. The verdict stays "untestable" because two comparison groups are below the sample size I set in advance.

The weights are up at huggingface.co/thanatchon36/cbtone-fomc-roberta-repl, under the same non-commercial licence as the training data and credited to the original authors. It's a replication, not their checkpoint: use theirs if you have access. The training script is in the repo too (about two hours on a MacBook Air M4).

Paper (updated): https://thanatchon36.github.io/cbtone/paper/
Chart: results/figures/fig_rq4b_fomc_f1.png

https://github.com/thanatchon36/cbtone
