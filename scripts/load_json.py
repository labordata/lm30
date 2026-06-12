"""Flatten the LM-30 report Part A/B/C blocks into the part_* tables.

form.json is {rptId: {part_a: [...], part_b: [...], part_c: [...]}},
derived from filing.jl (see common.mk). Each part is a list of entry
dicts; the flatten spec turns them into part_a / part_b / part_c rows
keyed (rptId, order), merged in ONE transaction via
olms.merge.load_tables (default strategy: delete the incoming rptIds and
re-insert, so a re-crawl of a filing replaces its rows).

    python scripts/load_json.py lm30.db form.json

Superseded-amendment orphans (a chain version evicted from filing whose
part rows linger) are swept by the Makefile / update.mk after this runs.
"""

import argparse
import json
import sqlite3
import sys

from olms.flatten import Table, flatten
from olms.merge import load_tables

PARTS_SPEC = [
    ("", Table("form", keys=("rptId",), emit=False)),
    ("*/part_a", Table("part_a", keys=("rptId", "part_a_order"), list_base=1)),
    ("*/part_b", Table("part_b", keys=("rptId", "part_b_order"), list_base=1)),
    ("*/part_c", Table("part_c", keys=("rptId", "part_c_order"), list_base=1)),
]

ORDER = ["part_a", "part_b", "part_c"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db")
    parser.add_argument("json_file")
    args = parser.parse_args()

    with open(args.json_file) as f:
        tables = flatten(json.load(f), PARTS_SPEC)

    conn = sqlite3.connect(args.db)
    reports = load_tables(conn, args.db, tables, ORDER)
    conn.close()
    for report in reports:
        print(report, file=sys.stderr)


if __name__ == "__main__":
    main()
