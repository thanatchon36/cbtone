# ruff: noqa: RUF001
from cbtone.text.clean import normalize


def test_dehyphenate_pdf_breaks():
    assert normalize("infla-\ntion is high") == "inflation is high"
    assert normalize("infla-\n  tion") == "inflation"
    # Capitalised continuation is a real hyphen/dash, keep it.
    assert normalize("Post-\nCovid") == "Post-\nCovid"


def test_quotes_dashes_zero_width():
    assert normalize("“hi” it’s 4–5") == '"hi" it\'s 4-5'
    assert normalize("a​b﻿c­d") == "abcd"
    assert normalize("rates—up") == "rates - up"


def test_nfkc_and_whitespace():
    assert normalize("ＡＢＣ  x\t\ty") == "ABC x y"
    assert normalize("a \n b\n\n\n\nc  ") == "a\nb\n\nc"
    assert normalize("a\r\nb") == "a\nb"


def test_idempotent():
    s = "“Infla-\ntion”  —  2.5–3 ％\n\n\n x"
    assert normalize(normalize(s)) == normalize(s)
