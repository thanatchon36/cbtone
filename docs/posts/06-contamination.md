Finding 6: how I checked whether the model had "seen the answers".

An LLM trained on the internet has probably read news about past rate decisions. If it scores a 2015 statement as hawkish because it remembers what happened next, that's leakage, not reading.

Two checks on every LLM result:
1. Masked text: bank names, committees, countries, dates and rate levels replaced with placeholders.
2. Post-cutoff split: only documents published after the model's release date.

A finding counts as robust only if it survives both.

Here, there was little to protect: the pooled gains were near zero with and without masking. The post-cutoff window has 58 decisions, too few to be informative, so I say "not established" rather than "robust".

The masking code is in the library if you want to run the same checks on your own signals.

https://github.com/thanatchon36/cbtone
