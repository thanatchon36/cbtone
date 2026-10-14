Finding 1: LLM tone does not beat "same as last time" at predicting the next rate decision.

For each bank I refit an ordered logit at every meeting using only past data, and asked whether adding the tone of the latest statement lowers the log-loss of the next decision versus a persistence baseline.

4 banks had enough hikes and cuts to test (Fed, ECB, RBA, BI). The LLM succeeded at none.

The ECB came closest: a gain with a confidence interval above zero, beating both placebo tests (shuffled dates, permuted labels). After correcting for testing four banks, p = 0.13. Not significant, so it's reported as such.

At the RBA, a plain dictionary did slightly better than the LLM.

The lesson I keep relearning: most of what is predictable about the next move is already in the last one.

Chart: results/figures/fig_rq1_dll.png

https://github.com/thanatchon36/cbtone
