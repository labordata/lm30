# update.mk — incremental update of lm30.db.
#
# Refresh the filer table from the full list (cheap: three pages),
# discover filers with new LM-30 activity
# (scripts/discover_new_filings.py — runs AFTER the filer refresh, so
# brand-new filers' srNums resolve to srFilerIds), crawl just those
# filers' detail feeds, and upsert. Paper filings this path can't see
# are reconciled by the monthly from-scratch rebuild
# (.github/workflows/full-build.yml).
#
# Usage: make -f update.mk update

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c

PRIOR_DB_URL ?= https://github.com/labordata/lm30/releases/download/nightly/lm30.db.zip

.DELETE_ON_ERROR:

.PHONY: update fk-check update_filer update_filing

# ============================================================================
# Entry
# ============================================================================

# The filer refresh and discovery must be fresh every run, so rebuild
# them once here, explicitly. Discovery reads the filer table, so the
# refresh comes first (no -j parallelism).
update: lm30.db
	rm -f filer.csv sr_nums.txt
	$(MAKE) -f update.mk update_filer
	$(MAKE) -f update.mk sr_nums.txt
	@if [ -s sr_nums.txt ]; then \
	    $(MAKE) -f update.mk update_filing; \
	else \
	    echo "update: no new filings discovered; only the filer table was refreshed" >&2; \
	fi
	@$(MAKE) -f update.mk fk-check

# ============================================================================
# Validation
# ============================================================================

fk-check:
	@violations=$$(sqlite3 lm30.db "PRAGMA foreign_key_check;" 2>&1); \
	if [ -n "$$violations" ]; then \
	    echo "fk-check: violations in lm30.db:" >&2; \
	    echo "$$violations" >&2; \
	    exit 1; \
	fi
	@echo "fk-check: lm30.db has no FK violations"

# ============================================================================
# Merges
# ============================================================================

update_filer: filer.csv | lm30.db
	python scripts/merge_csv.py lm30.db filer --replace --ignore filerType < $<

update_filing: filing.csv | lm30.db
	python scripts/merge_csv.py lm30.db filing --ignore formLink < $<

# ============================================================================
# Spider outputs
# ============================================================================

# Every discovered filer was discovered FROM a filing, so its detail
# feed must yield at least one item; fewer items than filers means the
# crawl was blocked (OLMS 403s), not that there was nothing to fetch.
filing.csv: filing.jl
	jq -rs '(map(keys) | add | unique) as $$cols | map(. as $$row | $$cols | map($$row[.])) as $$rows | $$cols, $$rows[] | @csv' $< > $@

filing.jl: sr_nums.txt
	scrapy crawl filings_incremental -L INFO -a sr_nums_file=$< -O $@
	@[ "$$(wc -l < $@)" -ge "$$(wc -l < $<)" ] || \
	    (echo "ERROR: $@ has fewer filings than discovered filers; crawl was likely blocked" >&2 && exit 1)

sr_nums.txt: | lm30.db
	python scripts/discover_new_filings.py lm30.db > $@

# The filer list always has thousands of filers; an empty crawl means
# something is broken (e.g. OLMS blocking us), not an empty list.
filer.csv:
	scrapy crawl filers -L INFO -O $@
	@[ "$$(wc -l < $@)" -gt 1 ] || (echo "ERROR: $@ is empty" >&2 && exit 1)

# Bootstrap: fetch the prior nightly release if no local lm30.db.
lm30.db:
	curl -fsSL -o prev.zip $(PRIOR_DB_URL)
	unzip -o prev.zip lm30.db
	rm -f prev.zip
