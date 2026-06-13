"""Flatten the LM-30 report Part A/B/C blocks into their tables.

form.json is {rptId: {part_a: [...], part_b: [...], part_c: [...]}},
derived from filing.jl (see common.mk). Each part is a list of entry
dicts keyed by the form's own part names; the flatten spec maps them to
descriptively named tables (Part A -> represented_employer_interest,
Part B -> business_interest, Part C -> other_employer_payment), rows
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
    ("*/part_a", Table("represented_employer_interest", keys=("rptId", "entry_order"), list_base=1)),
    ("*/part_b", Table("business_interest", keys=("rptId", "entry_order"), list_base=1)),
    ("*/part_c", Table("other_employer_payment", keys=("rptId", "entry_order"), list_base=1)),
]

ORDER = [
    "represented_employer_interest",
    "business_interest",
    "other_employer_payment",
]


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
