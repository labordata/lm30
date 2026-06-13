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

Amendments: an LM-30 amendment gets a **new rptId**, and the filer detail
feed serves only the latest version of each `(srFilerId, yrCovered)` chain
(GetLM30AmendmentReportsServlet exposes the full chain, superseded versions
included — a candidate `amendment` table for a later phase). The filing
merge therefore evicts all prior versions of an incoming row's chain, so
superseded versions never linger.

The form contents — the disclosure blocks that are the LM-30's substance —
are parsed from each electronic filing's report HTML into per-entry tables
(a filing can disclose several of each):

- `represented_employer_interest` (form Part A) — interests in, and
  payments from, an employer whose employees the filer's union represents
- `business_interest` (form Part B) — interests in businesses that deal
  with the union, its trusts, or the represented employer
- `other_employer_payment` (form Part C) — payments from other employers
  that would raise a conflict

Each is keyed `(rptId, entry_order)`. Coverage: OLMS serves each report as
either the "Revised 2011" HTML (which this parser reads) or a PDF, and the
filing index doesn't distinguish them. Sampling shows recent filings (2021+)
are ~100% HTML, so the nightly update parses everything it picks up; older
filings are predominantly PDF (the entire 2008-2014 era sampled as PDF) and
have no parsed parts, header, or `report_identity` row — capturing those
would require PDF text extraction, not more HTML parsing. There is no second
HTML markup: ~94 sampled reports were either Revised-2011 HTML or PDF, none
other. Many HTML reports are also nil (no Part entries).

- `amendment` — the full version chain of each amended filing, including
  the superseded versions the filer detail feed hides; backfilled from
  GetLM30AmendmentReportsServlet during the full build.

## How it updates

Nightly (`make -f update.mk update`): refresh the filer table from the full
list, discover filers with new electronic filings by forward-probing the
OLMS rptId space, crawl just those filers' detail feeds, and upsert.

Monthly (`make lm30.db`): full from-scratch rebuild — LM-30 archives no
documents, so unlike the sibling pipelines this fits a CI job — which also
picks up paper filings the electronic-only discovery can't see.
