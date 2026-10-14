Finding 4: reword the prompt, change the score.

I wrote five paraphrases of the same instruction ("classify this central-bank text as hawkish, dovish or neutral") and scored the same documents with each.

Agreement across prompts (Krippendorff's alpha): 0.65 for documents, 0.42 for sentences. My pre-set bar was 0.667.

Temperature mattered much less (alpha 0.92 for documents at 0 vs 0.7).

Swapping qwen3:4b for qwen2.5:3b mattered most: sentence-level agreement was no better than chance.

Practical takeaway: an LLM tone series is only comparable over time if the prompt and the model version are frozen and logged. Report a stability check next to any index.

https://github.com/thanatchon36/cbtone
