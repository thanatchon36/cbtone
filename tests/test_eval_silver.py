import polars as pl
import pytest

from cbtone.eval.silver import DEFAULT_QUOTAS, sample_silver


def _sentences() -> pl.DataFrame:
    rows = []
    for bank, lang in [("mas", "en"), ("bi", "en"), ("bi", "id"), ("bnm", "ms"), ("fed", "en")]:
        for d in range(40):
            for s in range(5):
                text = (
                    "short one"
                    if s == 0
                    else f"{bank} {lang} doc {d} sentence {s} has enough words"
                )
                rows.append(
                    (f"{bank}:2020-01-{d % 28 + 1:02d}:statement:{lang}:{d}", 0, s, text, lang)
                )
    return pl.DataFrame(
        rows, schema=["doc_id", "para_idx", "sent_idx", "text", "lang"], orient="row"
    )


def test_quotas_seed_and_filters():
    quotas = {("mas", "en"): 10, ("bi", "id"): 7}
    a = sample_silver(_sentences(), quotas, seed=1)
    b = sample_silver(_sentences(), quotas, seed=1)
    assert a.equals(b)  # deterministic
    assert a.columns == ["sample_id", "bank", "lang", "doc_id", "para_idx", "sent_idx"]
    counts = dict(
        a.group_by("bank", "lang").len().select(pl.concat_str("bank", "lang"), "len").rows()
    )
    assert counts == {"masen": 10, "biid": 7}
    assert sample_silver(_sentences(), quotas, seed=2)["doc_id"].to_list() != a["doc_id"].to_list()


def test_short_sentences_excluded_and_one_per_document_first():
    a = sample_silver(_sentences(), {("mas", "en"): 40}, seed=3)
    assert a["sent_idx"].min() >= 1  # the 2-word sentence is never drawn
    assert a["doc_id"].n_unique() == 40  # spread across documents before repeating one


def test_not_enough_sentences_raises():
    with pytest.raises(ValueError, match="bnm/ms"):
        sample_silver(_sentences(), {("bnm", "ms"): 10_000}, seed=1)


def test_default_quotas_total_200():
    assert sum(DEFAULT_QUOTAS.values()) == 200
    assert {b for b, _ in DEFAULT_QUOTAS} == {"mas", "bi", "bnm"}
