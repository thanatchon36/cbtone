# BIS central bank policy rates (WS_CBPOL)

- Dataset: BIS "Central bank policy rates", daily, SDMX dataflow `BIS/WS_CBPOL/1.0`.
- URL (fetched via `PoliteFetcher`, bank key `bis`, cached in `data/raw/bis/`):
  `https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.US+XM+GB+AU+ID+MY+CN+TH?format=csv&detail=dataonly&startPeriod=2008-01-01`
  (~1 MB). `detail=dataonly` drops the repeated metadata columns (the full file is ~20 MB).
  robots.txt at stats.bis.org did not block it.
- Terms: BIS statistics are published for public use with attribution; confirm the current wording
  at https://www.bis.org/terms_conditions.htm before redistributing (not independently verified here).
  The decisions table contains derived rate changes only.

## Which rate each series is (from the BIS series metadata)

| Bank | BIS series | First BIS observation (full history) | Used from |
|---|---|---|---|
| fed (US) | mid-point of the target range (single target before 2008-12-16) | 1954-07-01 | 2008-01-01 |
| ecb (XM) | **MRO fixed rate** to 2024-09-17; **DFR** from 2024-09-18 | 1999-01-01 | 2008-01-01 |
| boe (GB) | Bank Rate | 1946-01-01 | 2008-01-01 |
| rba (AU) | cash rate target | 1976-04-07 | 2008-01-02 |
| bi (ID) | BI policy rate | 2005-07-05 | 2008-01-01 |
| bnm (MY) | OPR | 1995-11-03 | 2008-01-01 |
| pboc (CN) | 1y LPR from 2019-08-20; 1y lending rate before | 1996-01-01 | 2008-01-01 |
| bot (TH) | 1-day repo rate (liquidity-providing) | 2000-05-23 | 2008-01-01 |

Adjustments in `cbtone.decisions.bis`:
- Fed: +12.5 bp from 2008-12-16 so `rate_after` is the upper bound (changes unaffected).
- ECB: the MRO -> DFR splice on 2024-09-18 would show -75 bp; the 12 Sep 2024 decision was a
  25 bp DFR cut (MRO cut 60 bp). We compare the first DFR print with `MRO - 50 bp`. Pre-2024
  ECB magnitudes are MRO magnitudes (the MRO moved with the DFR at most, not all, meetings).
- ECB MRO changes take effect up to ~6 days after the announcement, so the meeting-matching
  window is 7 days for the ECB (3 for others). Decision `date` = meeting date; the BIS change
  date is kept as `effective_date`.
- Observations below 0.5 bp in absolute change are dropped (BIS rounding blips, e.g. RBA
  Feb 2008). Missing (NaN) days are skipped; changes are between consecutive valid days.
- Singapore has no BIS series; MAS rows come from the text extractor (`source="mas_text"`).
