"""Output the amended (srFilerId, yrCovered) chains in lm30.db, one
"srFilerId,yrCovered" per line, as input for the amendments spider.

The filing table holds only the latest version of each chain; amended='Y'
marks the chains with superseded versions to backfill from
GetLM30AmendmentReportsServlet into the amendment table.

Usage: python scripts/amended_chains.py lm30.db
"""

import argparse
import sqlite3


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", help="lm30.db (reads the filing table)")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        "SELECT DISTINCT srFilerId, yrCovered FROM filing "
        "WHERE amended = 'Y' AND srFilerId IS NOT NULL AND yrCovered IS NOT NULL "
        "ORDER BY srFilerId, yrCovered"
    )
    for sr_filer_id, yr_covered in rows:
        print(f"{sr_filer_id},{yr_covered}")
    conn.close()


if __name__ == "__main__":
    main()
