from datetime import UTC, date, datetime

from cbtone.schema import Document, Section
from cbtone.text.paragraphs import policy_text, select_policy_paragraphs, tag_paragraph


def test_tags_en():
    assert (
        tag_paragraph("The Committee decided to raise the target range for the federal funds rate.")
        == "decision"
    )
    assert (
        tag_paragraph("The Committee will continue to monitor and stands ready to adjust.")
        == "forward_guidance"
    )
    assert (
        tag_paragraph("Inflation remains elevated and GDP growth slowed; unemployment rose.")
        == "outlook"
    )
    assert tag_paragraph("Downside risks and uncertainty have increased.") == "risks"
    assert tag_paragraph("For further information contact the media office.") == "boilerplate"
    assert tag_paragraph("Members were present.") == "other"


def test_tags_native():
    assert tag_paragraph("Rapat Dewan Gubernur memutuskan menurunkan BI-Rate", "id") == "decision"
    assert (
        tag_paragraph("MPC memutuskan untuk mengekalkan OPR pada 3.00 peratus", "ms") == "decision"
    )
    assert tag_paragraph("คณะกรรมการมีมติคงอัตราดอกเบี้ยนโยบาย", "th") == "decision"
    assert tag_paragraph("预计经济增长", "zh") == "outlook"


def test_priority_under_cap_and_document_order():
    paras = [
        "Inflation and growth outlook " * 10,  # outlook, 290 chars
        "Risks and uncertainty " * 10,  # risks
        "The Committee decided to keep the policy rate unchanged.",  # decision
    ]
    out = select_policy_paragraphs(paras, "en", cap=400)
    assert out[-1].startswith("The Committee decided")  # document order kept
    assert out[0].startswith("Inflation")  # outlook fits after the decision
    assert all(not p.startswith("Risks") for p in out)  # no room left for risks


def test_policy_text_falls_back_to_prefix():
    doc = Document(
        bank="fed",
        date=date(2020, 1, 1),
        doc_type="statement",
        language="en",
        title="t",
        text="Members were present. " * 400,
        sections=[Section(text="Members were present.")],
        url="https://x",
        sha256="0" * 64,
        fetched_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    assert policy_text(doc, cap=100) == doc.text[:100]
