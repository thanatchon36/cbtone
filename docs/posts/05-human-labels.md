Finding 5: against human labels, a 4B local model beats a dictionary but misses the bar.

On the public FOMC hawkish/dovish test set (496 human-labelled sentences, Shah et al. 2023; evaluation only, under its non-commercial licence):

- local LLM (qwen3:4b): macro-F1 0.48
- small fine-tuned multilingual model, trained only on the LLM's labels: 0.41
- my word-list dictionary: 0.27

I had pre-registered 0.50 for the LLM, so the hypothesis is refuted, even though it clearly beats the dictionary (difference 0.21, CI excluding zero).

For context, the published fine-tuned RoBERTa reaches about 0.72 on this set. It's a gated model and access never came, so I retrained it from the paper's recipe: my replication scores 0.71 (see post 10).

Both the dictionary and the LLM call too many sentences neutral.

Chart: results/figures/fig_rq4b_fomc_f1.png

https://github.com/thanatchon36/cbtone
