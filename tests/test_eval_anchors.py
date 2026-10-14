from datetime import UTC, datetime

import pytest

from cbtone.eval import anchors
from cbtone.sources.base import PoliteFetcher, RawResponse

CSV = (
    "﻿index,sentence,year,label,orig_index\n"
    "122,Broad equity price indexes fell sharply.,2011,2,119\n"
    '7,"Inflation pressures, members said, warranted firming.",2006,1,7\n'
    "9,The Committee will lower the target rate.,2008,0,9\n"
).encode()


class FakeFetcher(PoliteFetcher):
    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.calls: list[tuple[str, str]] = []

    def get(self, bank: str, url: str) -> RawResponse:
        self.calls.append((bank, url))
        return RawResponse(url, CSV, "text/csv", "00" * 32, datetime.now(UTC), from_cache=True)


def test_parse_maps_labels_and_strips_bom():
    df = anchors.parse_fomc_csv(CSV, "test")
    assert df.columns == ["sentence_id", "sentence", "year", "label", "split"]
    assert df["label"].to_list() == ["neutral", "hawkish", "dovish"]
    assert df["sentence_id"].to_list() == ["test:122", "test:7", "test:9"]
    assert df["sentence"][1] == "Inflation pressures, members said, warranted firming."


def test_parse_rejects_unknown_label():
    with pytest.raises(ValueError, match="label"):
        anchors.parse_fomc_csv(CSV.replace(b",2011,2,", b",2011,5,"), "train")


def test_load_uses_pinned_revision_for_each_split():
    f = FakeFetcher()
    df = anchors.load_fomc_anchor(f)
    assert df.height == 6 and set(df["split"]) == {"train", "test"}
    assert all(anchors.FOMC_REVISION in url for _, url in f.calls)
    assert {b for b, _ in f.calls} == {"fomc_anchor"}
