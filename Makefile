SHELL=/bin/bash

.DELETE_ON_ERROR:

# Full from-scratch build. LM-30 detail rows are flat and documents are
# not archived, so unlike the sibling pipelines this fits comfortably
# in a CI job: two row crawls and two merges.
lm30.db : schema.sql filer.csv filing.csv
	rm -f $@
	sqlite3 $@ < schema.sql
	python scripts/merge_csv.py $@ filer --replace --ignore filerType < filer.csv
	python scripts/merge_csv.py $@ filing --ignore formLink < filing.csv
	sqlite-utils vacuum $@
	@test -z "$$(sqlite3 $@ 'PRAGMA foreign_key_check;')" && echo "fk-check: $@ is clean"

filer.csv :
	scrapy crawl filers -L INFO -O $@
	@[ "$$(wc -l < $@)" -gt 1 ] || (echo "ERROR: $@ is empty" >&2 && exit 1)

filing.csv :
	scrapy crawl filings -L INFO -O $@
	@[ "$$(wc -l < $@)" -gt 1 ] || (echo "ERROR: $@ is empty" >&2 && exit 1)
