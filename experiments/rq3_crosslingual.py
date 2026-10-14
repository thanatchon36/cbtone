"""RQ3 table: native vs English consistency on parallel documents; H3 verdict.

Writes results/rq3_rows.csv and results/rq3.json.
"""

from __future__ import annotations

import polars as pl
from _common import LABELS_ALL, config, load_scores, write_json, write_rows

from cbtone.analysis.rq345 import rq3_rows, rq3_verdict


def main() -> None:
    scores = pl.concat([load_scores(), load_scores(native=True)], how="diagonal_relaxed")
    banks = ["bi", "bnm", "pboc"] + (["bot"] if config().get("include_bot") else [])
    labels = {k: LABELS_ALL[k] for k in ("llm", "ft", "dict")}
    rows = rq3_rows(scores, banks, labels)
    v = rq3_verdict(rows, llm="llm", required=("bi", "bnm"))
    write_rows("rq3_rows", rows)
    write_json("rq3", {"verdict": v, "rows": rows})
    print(v)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
