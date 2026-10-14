# Spec: literature review cluster

Output for cluster `<c>`: `docs/literature/cluster_<c>.md` and `docs/literature/refs_<c>.bib`.

- 8–12 sources per cluster. **Every source must be verified real** via web search (title, authors,
  year, venue; DOI or stable URL). Never cite from memory alone. If you cannot verify one, drop it.
- Per source, 80–150 words: question, data (banks, period, languages), method, main finding, and how
  it bears on cbtone (what we reuse, compare against, or fill a gap for). Note typical **effect sizes /
  accuracy numbers** where reported (we use them for the "> 2× off literature" sanity check): e.g.
  F1 of FOMC-RoBERTa, event-study R² of tone surprises, prediction accuracy of next decisions.
- End with a "gaps" paragraph: which bank × language × scorer × evaluation combinations this cluster
  leaves untested.
- BibTeX keys: `lastnameYEARword` (e.g. `shah2023trillion`). Neutral academic tone.
- Do not touch other files; don't commit. Final report ≤ 150 words: count, any doubtful items, the
  key numeric benchmarks.
