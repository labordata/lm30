"""lm30's table semantics for the olms merge engine.

Both tables are upserts on their primary keys — LM-30 amendments reuse
the same rptId, and filers are keyed by srFilerId — so no custom
strategies are needed:

    python scripts/merge_csv.py lm30.db filer --replace --ignore filerType < filer.csv
    python scripts/merge_csv.py lm30.db filing --replace --ignore formLink < filing.csv
"""

from olms.merge import main

if __name__ == "__main__":
    main(description=__doc__)
