# Prompt variants for `LLMScorer`

Five paraphrases of one task: give the probabilities that a text from a central-bank communication
signals a more hawkish (tighter), more dovish (looser) or neutral **future** monetary-policy stance.
They are the system message of every call; the text to score is the user message. All are bank-agnostic and
tell the model the text may be in English, Indonesian, Malay, Thai or Chinese. The JSON shape is enforced by
the request's JSON schema, not by the prompt.

| id | one-line class definitions | order of classes | other differences |
|----|----------------------------|------------------|-------------------|
| P1 | yes | hawkish, dovish, neutral | headline prompt; expert role; "base your judgement only on the text" |
| P2 | no | hawkish, dovish, neutral | phrased as a question; shortest |
| P3 | yes | neutral, dovish, hawkish | analyst role; examples of what each reading looks like |
| P4 | yes | dovish, hawkish, neutral | framed as "direction of the next policy moves", easing vs tightening |
| P5 | no | hawkish, dovish, neutral | output requirement first; warns against reading tone as sentiment |

`prompt_id` is `P<n>@<first 8 hex of the sha256 of the file bytes>`, so editing a file changes the id and
invalidates cached scores. Do not edit a prompt after scoring has started (pre-registration, RESEARCH_QUESTIONS.md §0.5).
