# ruff: noqa: RUF001
import pytest

from cbtone.text.langdetect import detect_language

CASES = [
    ("The Committee decided to maintain the target range for the federal funds rate.", "en"),
    (
        "Bank Indonesia memutuskan untuk mempertahankan BI-Rate karena inflasi yang terkendali.",
        "id",
    ),
    ("Kebijakan moneter tetap akan diarahkan bahwa inflasi tetap rendah sebesar 3 persen.", "id"),
    ("Bank Negara Malaysia mengekalkan kadar dasar semalaman kerana inflasi bagi tahun ini.", "ms"),
    ("Majlis Dasar Monetari memutuskan kadar kekal pada 3.00 peratus.", "ms"),
    ("中国人民银行货币政策委员会召开例会，强调稳健的货币政策。", "zh"),
    ("คณะกรรมการนโยบายการเงินมีมติให้คงอัตราดอกเบี้ยนโยบาย", "th"),
    ("MPC held the policy rate at 2.5 percent, citing 中国 demand", "en"),
]


@pytest.mark.parametrize(("text", "lang"), CASES)
def test_detect(text: str, lang: str):
    assert detect_language(text) == lang


def test_undetectable():
    assert detect_language("") is None
    assert detect_language("12345 !!!") is None
    assert detect_language("xyzzy plugh") is None
