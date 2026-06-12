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
