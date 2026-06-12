# common.mk — derive form.json (the report Part A/B/C blocks) from
# filing.jl, shared by the full build (Makefile) and the incremental
# update (update.mk). The spider target that produces filing.jl lives in
# the including makefile; form.json is loaded into the part_* tables by
# scripts/load_json.py.
#
# form.json is {rptId: {part_a, part_b, part_c}} for every filing whose
# report was fetched and parsed (electronic filings). Paper filings carry
# detailed_form_data = null and are skipped.

form.json : filing.jl
	cat $< \
	  | jq -c 'select(.detailed_form_data) | {rptId} + .detailed_form_data' \
	  | jq -s 'INDEX(.rptId | tostring) | with_entries(.value |= del(.rptId))' \
	  > $@
