# Market data sources (`cbtone.markets`)

Independent open-source research use only; not investment advice. Raw responses are cached under
`data/raw/{markets,fred,ecb_sdw,boe,rba}/` (FX as parquet + JSON sidecar with source, tickers,
retrieved_at, sha256; HTTP sources via `PoliteFetcher`, SHA-256 per response). All series are
`[date, series, close]`; yields in percent, converted to bp by `event_window`.

Close times live in `cbtone.markets.registry.REGISTRY` and are **conventions** (approximate), used
only to decide which close first reflects a release.

## Daily series

| Series | What | Source / URL | Range found | Close (tz) | Holidays |
|---|---|---|---|---|---|
| USDSGD=X, USDIDR=X, USDMYR=X, USDTHB=X, USDCNY=X, EURUSD=X, GBPUSD=X, AUDUSD=X | Spot FX | Yahoo Finance via `yfinance` | all 9 verified for 2024-06 | 17:00 America/New_York (Yahoo's daily bar rollover) | Weekdays only; Yahoo drops some days |
| DX-Y.NYB | ICE US Dollar Index | Yahoo Finance | verified | 17:00 America/New_York | ICE US |
| DGS2, DGS10 | US Treasury CMT 2y/10y | FRED `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>` (H.15) | long history | 15:30 America/New_York | US bond market; `.` rows dropped |
| EA2Y, EA10Y | Euro-area AAA govt spot curve | ECB Data Portal `https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{2Y,10Y}` | 2004-09-06 to latest | 17:30 Europe/Berlin (approx.) | TARGET days |
| GB2Y, GB10Y | UK gilt nominal GLC spot | BoE `.../files/statistics/yield-curves/glcnominalddata.zip` (xlsx, sheet "4. spot curve") | 1979 to latest | 16:00 Europe/London (approx.) | UK business days |
| AU2Y, AU10Y | Australian govt bond yields | RBA table F2 `https://www.rba.gov.au/statistics/tables/csv/f2-data.csv` | 10y from 2013-05-20; 2y from 2013-09-02 | 16:00 Australia/Sydney (approx.) | AU business days |

## Terms
* Yahoo Finance: personal/research use only; data is not redistributable. Do not commit raw FX
  parquet to a public release without checking; derived event-window changes are fine to publish.
* FRED: H.15 data is public domain (Federal Reserve Board); FRED terms ask for citation.
* ECB: free reuse with source acknowledgement.
* BoE: Open Government-style terms; cite "Bank of England".
* RBA: copyright RBA, reuse with attribution.
(Exact wording to be added to `docs/sources/LICENSES.md` by the sources owner.)

## Gaps and notes
* FRED's UK/EA/AU yields (`IRLTLT01...`) are monthly OECD series and unusable for event windows,
  hence ECB / BoE / RBA official daily files above.
* BoE: `_iadb-FromShowColumns.asp` (IADB CSV) is disallowed by robots.txt, so it is not used. The
  xlsx archive is ~40 MB (fetched once, cached; `.bin` is gitignored). Only 2y/10y spot are read.
  RBA's `f2-data.csv` is returned only to a non-browser User-Agent; curl's default is denied.
* RBA F2 2y/10y begin in 2013; earlier history is in separate RBA historical tables (not used).
* **SG / MY / TH / ID yields: skipped, FX only.** MAS SGS yields are on an interactive ASP.NET
  page (`eservices.mas.gov.sg/statistics/fdanet/BenchmarkPricesAndYields.aspx`), no CSV endpoint
  found, and MAS is known to block automation. BNM's Open API (`api.bnm.gov.my`, moved to
  `apikijangportal.bnm.gov.my`) has no MGS yield endpoint that I could find; BoT and BI publish
  yields via HTML pages / the third-party ThaiBMA, not a login-free CSV. If a manual download is
  wanted, list under `docs/sources/NEEDED.md`.
* Yahoo FX closes are not exchange-grade; Asian-hours moves of a given day sit in that day's bar.
  A release on day D after 17:00 New York belongs to D+1's bar.
* Event-window rule (`event_window`): `t` = first close, by each series' own close time, strictly
  after the release instant; window is [t+pre, t+post] closes, default [t-1, t+1] (MISSION 1.3).
  `post=0` gives the tight [t-1, t]. FX -> log return; yields -> bp. Series with no data on either
  side or a data hole > 5 days after the event are omitted. Example: FOMC 14:00 ET (19:00 UTC)
  precedes the US 15:30 ET close (t = same day) but follows London, Berlin and Sydney closes
  (t = next day for GB/EA/AU yields).
