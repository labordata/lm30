"""Discover filers (srFilerIds) with new LM-30 activity since
lm30.db's max rptId.

Electronic LM-30 reports use a different markup dialect from the
sibling forms (rpt-instruction/rpt-data instead of i-label/i-value)
and show the filer's file number ("U-" + srNum), while the detail
servlet is keyed by srFilerId — so discovered srNums are mapped
through the filer table, which the update refreshes immediately before
discovery runs. srFilerIds go to stdout, one per line.

Paper LM-30s come back as PDFs we can't trivially parse; the monthly
from-scratch rebuild (.github/workflows/full-build.yml) picks them up.

Usage: python scripts/discover_new_filings.py lm30.db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from parsel import Selector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from olms.discover import DiscoveryConfig, discover  # noqa: E402


def extract_sr_num(html_bytes):
    sel = Selector(text=html_bytes.decode("utf-8", errors="replace"))
    val = sel.xpath(
        "//div[@class='rpt-instruction'][contains(., 'LM-30 File Number')]"
        "//span[@class='rpt-data']/text()"
    ).get()
    return int(val.strip()) if val and val.strip().isdigit() else None


CONFIG = DiscoveryConfig(
    watermark_sql="SELECT max(rptId) FROM filing",
    scan_forms=("LM30Form",),
    extractor=extract_sr_num,
    description=__doc__,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", help="lm30.db (reads max rptId and the filer table)")
    args = ap.parse_args()

    sr_nums = discover(CONFIG, args.db)

    # one srNum (a person's file number) can map to several srFilerIds
    # (one per union relationship); the detail servlet wants the latter
    conn = sqlite3.connect(args.db)
    sr_filer_ids = set()
    for sr in sr_nums:
        matches = [
            row[0]
            for row in conn.execute(
                "SELECT srFilerId FROM filer WHERE srNum = ?", (sr,)
            )
        ]
        if not matches:
            print(
                f"# srNum {sr} not in the filer table — refresh filers"
                " before discovery",
                file=sys.stderr,
            )
        sr_filer_ids.update(matches)
    conn.close()

    for sr_filer_id in sorted(sr_filer_ids):
        print(sr_filer_id)


if __name__ == "__main__":
    main()
