"""Collect results/rq*.json into results/summary.json and enforce the sanity rules (MISSION §0).

Every headline number is checked with ``cbtone.eval.rules.sanity_flags``. A flag fails the build
(exit 1) unless docs/ANOMALIES.md contains the line ``SANITY-OK: <flag key>`` with an
explanation. Flags and their status are written to results/SANITY.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import RESULTS, write_json

from cbtone.eval.rules import sanity_flags

ANOMALIES = Path("docs/ANOMALIES.md")


def _load(name: str) -> dict[str, Any]:
    p = RESULTS / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def headline_numbers(s: dict[str, Any]) -> list[tuple[str, float, str]]:
    """(key, value, kind) for every number the paper reports as a headline."""
    out: list[tuple[str, float, str]] = []
    for r in s.get("rq1", {}).get("rows", []):
        if r.get("powered") and r.get("scorer") in ("llm", "dict") and r.get("auroc") is not None:
            out.append((f"rq1.{r['bank']}.{r['scorer']}.auroc", r["auroc"], "metric"))
    for r in s.get("rq2", {}).get("rows", []):
        if r.get("powered") and r.get("subset") == "all" and r.get("r2") is not None:
            out.append((f"rq2.{r['bank']}.{r['kind']}.{r['scorer']}.r2", r["r2"], "metric"))
    for r in s.get("rq3", {}).get("rows", []):
        if r.get("status") == "ok":
            out.append((f"rq3.{r['bank']}.{r['scorer']}.spearman", r["spearman"], "corr"))
    for r in s.get("rq4", {}).get("rq4b", {}).get("rows", []):
        name = {
            "dict": "fomc_f1_dictionary",
            "llm": "fomc_f1_llm_zero_shot",
            "ft": "fomc_f1_finetuned",
            "fomc_roberta": "fomc_f1_fomc_roberta",
        }.get(r["scorer"], f"rq4b.{r['scorer']}.macro_f1")
        out.append((name, r["macro_f1"], "metric"))
    agg = s.get("rq4", {}).get("rq4a", {}).get("aggregation", {}).get("spearman", {})
    for k, v in agg.items():
        out.append((f"rq4a.aggregation.{k}", v, "corr"))
    for unit in ("sentences", "docs"):
        block = s.get("rq4", {}).get("rq4a", {}).get(unit, {})
        for part in ("prompts", "temperature", "model_tag"):
            if isinstance(block.get(part), dict) and block[part].get("alpha") is not None:
                out.append((f"rq4a.{unit}.{part}.alpha", block[part]["alpha"], "corr"))
    return out


def main() -> int:
    summary: dict[str, Any] = {name: _load(name) for name in ("rq1", "rq2", "rq3", "rq4", "rq5")}
    summary["corpus_version"] = Path("data/corpus/VERSION").read_text().strip()
    summary["timing"] = (
        json.loads((RESULTS / "timing.json").read_text())
        if (RESULTS / "timing.json").exists()
        else []
    )
    summary["hardware"] = (
        json.loads((RESULTS / "hardware.json").read_text())
        if (RESULTS / "hardware.json").exists()
        else {}
    )
    explained = (
        set(re.findall(r"SANITY-OK:\s*(\S+)", ANOMALIES.read_text()))
        if ANOMALIES.exists()
        else set()
    )
    flags = []
    for key, value, kind in headline_numbers(summary):
        if value is None:
            continue
        for reason in sanity_flags(key, float(value), kind):
            flags.append(
                {"key": key, "value": value, "reason": reason, "explained": key in explained}
            )
    summary["sanity"] = flags
    write_json("summary", summary)
    lines = ["# Sanity flags", "", "| key | value | reason | explained |", "|---|---|---|---|"]
    for f in flags:
        ok = "yes" if f["explained"] else "**no**"
        lines.append(f"| {f['key']} | {f['value']:.4f} | {f['reason']} | {ok} |")
    (RESULTS / "SANITY.md").write_text("\n".join(lines) + "\n")
    unexplained = [f for f in flags if not f["explained"]]
    print(f"{len(flags)} sanity flags, {len(unexplained)} unexplained")
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
