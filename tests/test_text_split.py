# ruff: noqa: RUF001
import pytest

from cbtone.text.split import split_paragraphs, split_sentences


def test_paragraphs():
    assert split_paragraphs("A b.\n\n\n  C d.\n \nE.\n") == ["A b.", "C d.", "E."]
    assert split_paragraphs("") == []


def test_en_abbreviations_and_decimals():
    text = (
        "Mr. Powell said the U.S. economy grew 2.5 percent. Dr. Lee e.g. disagreed. "
        "Inflation fell to 3.1% in Jan. 2024. The U.S. The Fed held rates."
    )
    out = split_sentences(text, "en")
    assert out == [
        "Mr. Powell said the U.S. economy grew 2.5 percent.",
        "Dr. Lee e.g. disagreed.",
        "Inflation fell to 3.1% in Jan. 2024.",
        "The U.S.",
        "The Fed held rates.",
    ]


def test_en_question_quotes_and_newlines():
    text = 'He asked, "Is it over?" She said no! Wait\nfor data.\n\nNew paragraph here.'
    assert split_sentences(text, "en") == [
        'He asked, "Is it over?"',
        "She said no!",
        "Wait for data.",
        "New paragraph here.",
    ]


def test_en_initials_not_split():
    assert split_sentences("J. P. Morgan expects cuts. Others differ.", "en") == [
        "J. P. Morgan expects cuts.",
        "Others differ.",
    ]


def test_id_ms_currency_and_company_abbrevs():
    id_text = "BI menaikkan suku bunga sebesar Rp. 5 triliun. PT Bank Tbk. Namun inflasi turun."
    assert split_sentences(id_text, "id") == [
        "BI menaikkan suku bunga sebesar Rp. 5 triliun.",
        "PT Bank Tbk.",
        "Namun inflasi turun.",
    ]
    ms_text = "Maybank Bhd. Menurut Dr. Aziz, kadar kekal 3.00 peratus. Ekonomi berkembang."
    assert split_sentences(ms_text, "ms") == [
        "Maybank Bhd. Menurut Dr. Aziz, kadar kekal 3.00 peratus.",
        "Ekonomi berkembang.",
    ]


def test_zh_punctuation_and_quotes():
    text = "央行宣布降准。市场反应积极！他说：“政策将保持稳健。”随后离开；会议结束\n下一行没有标点"
    assert split_sentences(text, "zh") == [
        "央行宣布降准。",
        "市场反应积极！",
        "他说：“政策将保持稳健。”",
        "随后离开；",
        "会议结束",
        "下一行没有标点",
    ]


def test_thai_with_pythainlp():
    pytest.importorskip("pythainlp")
    pytest.importorskip("pycrfsuite")
    out = split_sentences("คณะกรรมการมีมติคงอัตราดอกเบี้ยนโยบาย เศรษฐกิจมีแนวโน้มขยายตัว", "th")
    assert len(out) >= 1
    assert "".join(out).replace(" ", "") == "คณะกรรมการมีมติคงอัตราดอกเบี้ยนโยบายเศรษฐกิจมีแนวโน้มขยายตัว"


def test_thai_fallback_warns(monkeypatch: pytest.MonkeyPatch):
    import builtins

    real = builtins.__import__

    def fake(name: str, *a: object, **k: object):  # type: ignore[no-untyped-def]
        if name.startswith("pythainlp"):
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.warns(UserWarning, match="pythainlp"):
        out = split_sentences("ประโยคแรก ประโยคสอง\nประโยคสาม", "th")
    assert out == ["ประโยคแรก", "ประโยคสอง", "ประโยคสาม"]
