# lm30

Nightly-updated database of [LM-30 filings](https://www.dol.gov/agencies/olms/reports/forms/lm-30)
— union officer and employee conflict-of-interest reports — scraped from the
DOL OLMS [Online Public Disclosure Room](https://olmsapps.dol.gov/olpdr/).

Built on the shared [olms](https://github.com/labordata/olms) scraping
infrastructure, like its siblings [lm10](https://github.com/labordata/lm10)
and [lm20](https://github.com/labordata/lm20).

## Tables

- `filer` — one row per LM-30 filer (a union officer or employee and the
  union relationship they report under), keyed by `srFilerId`. A person
  (`srNum`, the "U-" file number) can have several `srFilerId`s.
- `filing` — one row per filing, keyed by `rptId`, with the period covered,
  receive/register dates, the union, and `filing_url` pointing at the
  report. Documents are not archived (yet); the `file_*` columns are
  reserved for that.

## How it updates

Nightly (`make -f update.mk update`): refresh the filer table from the full
list, discover filers with new electronic filings by forward-probing the
OLMS rptId space, crawl just those filers' detail feeds, and upsert.

Monthly (`make lm30.db`): full from-scratch rebuild — LM-30 archives no
documents, so unlike the sibling pipelines this fits a CI job — which also
picks up paper filings the electronic-only discovery can't see.
