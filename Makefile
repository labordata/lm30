SHELL=/bin/bash

.DELETE_ON_ERROR:

# Full from-scratch build. LM-30 detail rows are flat and documents are
# not archived, so unlike the sibling pipelines this fits comfortably
# in a CI job: two row crawls, the report-content parse, and the merges.
lm30.db : schema.sql filer.csv filing.csv form.json
	rm -f $@
	sqlite3 $@ < schema.sql
	python scripts/merge_csv.py $@ filer --replace --ignore filerType < filer.csv
	python scripts/merge_csv.py $@ filing --ignore formLink --ignore detailed_form_data < filing.csv
	python scripts/load_json.py $@ form.json
	sqlite3 $@ "DELETE FROM report_identity WHERE rptId NOT IN (SELECT rptId FROM filing); DELETE FROM represented_employer_interest WHERE rptId NOT IN (SELECT rptId FROM filing); DELETE FROM business_interest WHERE rptId NOT IN (SELECT rptId FROM filing); DELETE FROM other_employer_payment WHERE rptId NOT IN (SELECT rptId FROM filing);"
	python scripts/amended_chains.py $@ > amended_chains.txt
	scrapy crawl amendments -L INFO -a chains_file=amended_chains.txt -O amendment.jl
	jq -rs '(map(keys) | add | unique) as $$cols | map(. as $$row | $$cols | map($$row[.])) as $$rows | $$cols, $$rows[] | @csv' amendment.jl > amendment.csv
	python scripts/merge_csv.py $@ amendment --ignore formId --ignore formLink --ignore registerDate < amendment.csv
	sqlite-utils vacuum $@
	@test -z "$$(sqlite3 $@ 'PRAGMA foreign_key_check;')" && echo "fk-check: $@ is clean"

filer.csv :
	scrapy crawl filers -L INFO -O $@
	@[ "$$(wc -l < $@)" -gt 1 ] || (echo "ERROR: $@ is empty" >&2 && exit 1)

# jl is lossless: the CSV header is the union of keys across ALL rows
# (scrapy's CSV feed would silently truncate to the first item's
# fields), so a new upstream field becomes a loud unknown-column error
# in the merge instead of silent loss. detailed_form_data (the nested
# Part A/B/C blocks) is dropped here — it goes to the part_* tables via
# form.json (see common.mk), not into the flat filing row.
filing.csv : filing.jl
	jq -rs 'map(del(.detailed_form_data)) | (map(keys) | add | unique) as $$cols | map(. as $$row | $$cols | map($$row[.])) as $$rows | $$cols, $$rows[] | @csv' $< > $@

filing.jl :
	scrapy crawl filings -L INFO -O $@
	@[ "$$(wc -l < $@)" -gt 1 ] || (echo "ERROR: $@ is empty" >&2 && exit 1)

include common.mk
