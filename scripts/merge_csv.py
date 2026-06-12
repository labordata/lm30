"""lm30's table semantics for the olms merge engine.

    python scripts/merge_csv.py lm30.db filer --replace --ignore filerType < filer.csv
    python scripts/merge_csv.py lm30.db filing --ignore formLink < filing.csv

- filer: upsert on the srFilerId primary key (--replace).
- filing: LM-30 amendments get a NEW rptId, and the detail feed serves
  only the latest version of each (srFilerId, yrCovered) chain — the
  same key GetLM30AmendmentReportsServlet uses — so an incoming row
  evicts ALL prior versions of its chain, not just its own rptId.
  Otherwise a superseded version we crawled while it was latest would
  linger as a ghost row.
"""

from olms.merge import insert_rows, main


def merge_filing(conn, table, columns, rows):
    chains = {(int(row["srFilerId"]), int(row["yrCovered"])) for row in rows}
    deleted = 0
    for sr_filer_id, yr_covered in sorted(chains):
        cursor = conn.execute(
            "DELETE FROM filing WHERE srFilerId = ? AND yrCovered = ?",
            (sr_filer_id, yr_covered),
        )
        deleted += cursor.rowcount
    return deleted, insert_rows(conn, table, columns, rows)


STRATEGIES = {"filing": merge_filing}

if __name__ == "__main__":
    main(strategies=STRATEGIES, description=__doc__)
