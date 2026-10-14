# ruff: noqa: RUF001
import pytest

from cbtone.text.mask import mask_entities

CASES = [
    ("The Federal Reserve raised rates.", "The [BANK] raised rates."),
    ("The Fed and the ECB acted; FOMC met.", "The [BANK] and the [BANK] acted; [BANK] met."),
    ("the Monetary Authority of Singapore (MAS) said", "the [BANK] ([BANK]) said"),
    ("Bank of England and Bank Negara Malaysia", "[BANK] and [BANK]"),
    ("S$NEER appreciates", "[CURRENCY] NEER appreciates"),
    ("the rupiah and the ringgit and euro", "the [CURRENCY] and the [CURRENCY] and [CURRENCY]"),
    ("The euro area and Singapore grew", "The [COUNTRY] and [COUNTRY] grew"),
    ("the U.S. economy and the UK", "the [COUNTRY] economy and the [COUNTRY]"),
    ("raised to 5.25 percent", "raised to [RATE]"),
    ("a range of 4.25-4.50 per cent", "a range of [RATE]"),
    ("cut by 25 basis points", "cut by [BP]"),
    ("a 50bps hike and 25-basis-point cut", "a [BP] hike and [BP] cut"),
    ("rate of 4¾% and 1/4 percentage point", "rate of [RATE] and [RATE]"),
    ("a quarter-point move", "a [RATE] move"),
    ("on 14 March 2024 and March 14, 2024", "on [DATE] and [DATE]"),
    ("in 2024Q1, Q2 2025 and 1999", "in [DATE], [DATE] and [DATE]"),
    ("Jan. 31 meeting", "[DATE] meeting"),
    ("2024年3月21日会议；降息25个基点至3.5%", "[DATE]会议；降息[BP]至[RATE]"),
    ("BI-Rate 6,00 persen, Maret 2024", "[POLICY_RATE] [RATE], [DATE]"),
]


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_mask(text: str, expected: str):
    assert mask_entities(text) == expected


@pytest.mark.parametrize(("text", "_"), CASES)
def test_idempotent(text: str, _: str):
    once = mask_entities(text)
    assert mask_entities(once) == once


def test_generic_words_untouched():
    s = "Inflation and growth eased; the Committee judged risks balanced. We may act in May."
    out = mask_entities(s)
    assert out == s
    assert mask_entities("The Committee met in May 2024.") == "The Committee met in [DATE]."


def test_instruments_committees_and_hyphen_fractions_are_masked():
    from cbtone.text.mask import mask_entities as m

    out = m(
        "The Committee decided to raise the target range for the federal funds rate to 5-1/4 to 5-1/2 percent."
    )
    assert (
        "federal funds" not in out
        and "5-1/4" not in out
        and "[POLICY_RATE]" in out
        and "[RATE]" in out
    )
    assert (
        m("The MPC voted to maintain Bank Rate at 5.25%.")
        == "The [COMMITTEE] voted to maintain [POLICY_RATE] at [RATE]."
    )
    assert "Governing Council" not in m(
        "the Governing Council decided to lower the deposit facility rate."
    )
    assert m("Rapat Dewan Gubernur memutuskan BI-Rate") == "[COMMITTEE] memutuskan [POLICY_RATE]"
    assert "cash rate" not in m("The Reserve Bank Board left the cash rate target unchanged.")
    assert "policy band" in m(
        "MAS will maintain the slope of the S$NEER policy band."
    )  # meaning kept
    t = m("Bank Negara Malaysia kept the Overnight Policy Rate (OPR) at 3.00 percent.")
    assert m(t) == t  # idempotent
