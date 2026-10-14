# Adapters

One adapter per bank (`src/cbtone/sources/<bank>.py`), each documented in
`docs/sources/<bank>.md`. All HTTP goes through `PoliteFetcher`: it honours `robots.txt`, waits
at least 2 s between requests to a host, identifies itself with a descriptive User-Agent, and
caches every raw response under `data/raw/<bank>/` with its SHA-256.

Counts are from corpus snapshot `2026-10-14+ed5a49c2...` (see
[PROGRESS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/PROGRESS.md)).

| Bank | Code | Documents | Languages | Role | Text redistributable | Source notes |
|---|---|---|---|---|---|---|
| Federal Reserve | `fed` | 535 | en | headline | yes | [fed.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/fed.md) |
| European Central Bank | `ecb` | 575 | en | headline | statements yes; press conferences no | [ecb.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/ecb.md) |
| Bank of England | `boe` | 567 | en | headline | no | [boe.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/boe.md) |
| Reserve Bank of Australia | `rba` | 452 | en | headline | yes (CC BY 4.0) | [rba.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/rba.md) |
| Monetary Authority of Singapore | `mas` | 62 | en | headline | no | [mas.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/mas.md) |
| Bank Indonesia | `bi` | 256 | en, id | headline | no | [bi.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/bi.md) |
| Bank Negara Malaysia | `bnm` | 280 | en, ms | headline | no | [bnm.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/bnm.md) |
| Bank of Thailand | `bot` | 143 | th, en | opt-in, excluded from headline | no | [bot.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/bot.md) |
| People's Bank of China | `pboc` | 65 | zh | exploratory | no | [pboc.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/pboc.md) |
| BIS policy rates (decision table input) | n/a | n/a | n/a | data source | see notes | [bis.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/bis.md) |
| Market series | n/a | n/a | n/a | data source | not committed | [markets.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/markets.md) |

Terms of use for every source, and what is committed for each, are in
[LICENSES.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/LICENSES.md). If a site blocks automated access, the
adapter stops for that bank and the URLs a human should download are listed in
[NEEDED.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/NEEDED.md) (MAS is the known case).

To add a bank, see the [cookbook](cookbook.md#add-a-central-bank-in-30-lines).
