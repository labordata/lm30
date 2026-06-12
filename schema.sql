CREATE TABLE IF NOT EXISTS "filer" (
   [srFilerId] INTEGER PRIMARY KEY,
   [srNum] INTEGER,
   [name] TEXT,
   [suffix] TEXT,
   [city] TEXT,
   [state] TEXT,
   [affAbbr] TEXT,
   [unionName] TEXT,
   [unionCity] TEXT,
   [unionState] TEXT,
   [detailId] INTEGER
);
CREATE TABLE IF NOT EXISTS "filing" (
   [rptId] INTEGER PRIMARY KEY,
   [srFilerId] INTEGER REFERENCES [filer]([srFilerId]),
   [amended] TEXT,
   [amendment] INTEGER,
   [beginDate] TEXT,
   [endDate] TEXT,
   [receiveDate] TEXT,
   [registerDate] TEXT,
   [formFiled] TEXT,
   [yrCovered] INTEGER,
   [unionName] TEXT,
   [unionCity] TEXT,
   [unionState] TEXT,
   [filing_url] TEXT,
   [file_path] TEXT,
   [file_checksum] TEXT,
   [file_status] TEXT
);
-- Part A/B/C: the report's disclosure blocks, parsed from the LM-30
-- report HTML (orgReport.do), one row per entry. Keyed (rptId, order);
-- rptId references the current filing version. Superseded-amendment
-- orphans (a chain version evicted from filing) are swept after load in
-- the Makefile / update.mk.
CREATE TABLE IF NOT EXISTS "part_a" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [part_a_order] INTEGER,
   [represented_employer] TEXT,
   [contact_name] TEXT,
   [telephone] TEXT,
   [street] TEXT,
   [city] TEXT,
   [state] TEXT,
   [zip] TEXT,
   [nature_of_interest] TEXT,
   [amount] TEXT,
   PRIMARY KEY ([rptId], [part_a_order])
);
CREATE TABLE IF NOT EXISTS "part_b" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [part_b_order] INTEGER,
   [business_name] TEXT,
   [contact_name] TEXT,
   [telephone] TEXT,
   [street] TEXT,
   [city] TEXT,
   [state] TEXT,
   [zip] TEXT,
   [deals_with] TEXT,
   [deals_with_name] TEXT,
   [deals_with_contact_name] TEXT,
   [deals_with_telephone] TEXT,
   [deals_with_street] TEXT,
   [deals_with_city] TEXT,
   [deals_with_state] TEXT,
   [deals_with_zip] TEXT,
   [nature_of_dealings] TEXT,
   [value_of_dealings] TEXT,
   [nature_of_interest] TEXT,
   [amount_of_interest] TEXT,
   PRIMARY KEY ([rptId], [part_b_order])
);
-- Part C is MODELED, not yet validated against a real populated sample
-- (they are rare); the Makefile / update.mk tripwire asserts it is empty
-- so the first real one fails the build loudly. See the parser notes.
CREATE TABLE IF NOT EXISTS "part_c" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [part_c_order] INTEGER,
   [other_employer] TEXT,
   [contact_name] TEXT,
   [telephone] TEXT,
   [street] TEXT,
   [city] TEXT,
   [state] TEXT,
   [zip] TEXT,
   [nature_of_interest] TEXT,
   [amount] TEXT,
   PRIMARY KEY ([rptId], [part_c_order])
);
