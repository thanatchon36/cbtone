"""Minimal read-only .xlsx reader (stdlib only) for the Bank of England yield workbooks."""

from __future__ import annotations

import io
import re
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree as ET

_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}
Cell = str | float | None
Row = dict[str, Cell]


def excel_date(serial: float) -> date:
    return date(1899, 12, 30) + timedelta(days=int(serial))


def _col(ref: str) -> str:
    return re.sub(r"\d+", "", ref)


def read_sheet(xlsx: bytes, name_contains: str) -> list[Row]:
    """Rows (col letter -> value) of the first sheet whose name contains ``name_contains``."""
    z = zipfile.ZipFile(io.BytesIO(xlsx))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall("p:Relationship", _NS)}
    target = None
    for sh in wb.findall("m:sheets/m:sheet", _NS):
        if name_contains.lower() in sh.attrib["name"].lower():
            target = targets[sh.attrib[f"{{{_NS['r']}}}id"]]
            break
    if target is None:
        raise KeyError(f"no sheet matching {name_contains!r}")
    path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"

    strings: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in sst.findall("m:si", _NS):
            strings.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))

    rows: list[Row] = []
    sheet = ET.fromstring(z.read(path))
    for row in sheet.findall("m:sheetData/m:row", _NS):
        out: Row = {}
        for c in row.findall("m:c", _NS):
            v = c.find("m:v", _NS)
            if v is None or v.text is None:
                continue
            col = _col(c.attrib["r"])
            if c.attrib.get("t") == "s":
                out[col] = strings[int(v.text)]
            elif c.attrib.get("t") in ("str", "inlineStr"):
                out[col] = v.text
            else:
                out[col] = float(v.text)
        rows.append(out)
    return rows
