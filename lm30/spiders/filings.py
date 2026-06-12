from email.message import Message

from scrapy import Spider
from scrapy.http import Request

from olms.http import form_request
from olms.spiders import SrNumSpiderMixin

# Identity sub-block labels shared by the represented employer (Part A),
# the business (Part B), the trust/employer named in Part B item 10, and
# the other employer (Part C).
IDENTITY = {
    "Contact name": "contact_name",
    "Telephone": "telephone",
    "Street Address": "street",
    "City": "city",
    "State": "state",
    "ZIP": "zip",
}


class LM30(Spider):
    """One row per LM-30 filing, from each filer's detail feed, enriched
    with the report's Part A/B/C disclosure blocks parsed from the report
    HTML (orgReport.do). The detail feed is the filing index; the Part
    blocks — the actual conflict-of-interest disclosures — live only in
    the rendered report, so each electronic filing's report is fetched
    and parsed into detailed_form_data."""

    name = "filings"

    custom_settings = {
        "ITEM_PIPELINES": {
            "olms.pipelines.TimestampToDatetime": 1,
        }
    }

    async def start(self):
        yield form_request(
            "https://olmsapps.dol.gov/olpdr/GetLM30FilerListServlet",
            formdata={"clearCache": "F", "page": "1"},
            cb_kwargs={"page": 1, "seen": 0},
            callback=self.parse,
        )

    def parse(self, response, page, seen):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM30FilerListServlet
        @filers_form
        @cb_kwargs {"page": 1, "seen": 0}
        @returns requests 501
        """
        data = response.json()
        filers = data["filerList"]
        for filer in filers:
            yield self._detail_request(filer["srFilerId"])

        seen += len(filers)
        if filers and seen < data["totalRecords"]:
            page += 1
            yield form_request(
                "https://olmsapps.dol.gov/olpdr/GetLM30FilerListServlet",
                formdata={"clearCache": "F", "page": str(page)},
                cb_kwargs={"page": page, "seen": seen},
                callback=self.parse,
            )

    def _detail_request(self, sr_filer_id):
        return form_request(
            "https://olmsapps.dol.gov/olpdr/GetLM30FilerDetailServlet",
            formdata={"srFilerId": str(sr_filer_id)},
            callback=self.parse_filings,
        )

    def parse_filings(self, response):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM30FilerDetailServlet
        @filings_form
        @returns items 1
        """
        for filing in response.json()["detail"]:
            filing["filing_url"] = (
                "https://olmsapps.dol.gov/query/orgReport.do"
                "?rptId={rptId}&rptForm={formLink}".format(**filing)
            )
            filing["detailed_form_data"] = None

            # Electronic filings render an HTML report with the Part
            # blocks; paper filings (no receiveDate, or pre-electronic
            # rptIds) have no report to parse. The 183135 cutoff is the
            # shared OLMS electronic-era rptId boundary (see lm20).
            electronic = filing.get("receiveDate") and filing["rptId"] > 183135
            if electronic:
                yield Request(
                    filing["filing_url"],
                    cb_kwargs={"item": filing},
                    callback=self.parse_html_report,
                )
            else:
                yield filing

    def parse_html_report(self, response, item, attempts=0):
        # OLMS sometimes serves a PDF instead of the HTML report; retry a
        # few times for the HTML before giving up (mirrors lm20).
        content_type_header = response.headers.get("Content-Type")
        if content_type_header:
            m = Message()
            m["content-type"] = content_type_header.decode()
            content_type = m.get_content_type()
        else:
            content_type = None

        if content_type == "text/html" and b"rpt-part-name" in response.body:
            item["detailed_form_data"] = LM30Report.parse(response)
            yield item
            return

        if attempts > 2:
            self.logger.warning(
                "giving up on %s after %d attempts (content type %r)",
                response.request.url,
                attempts + 1,
                content_type,
            )
            yield item
            return

        yield Request(
            response.request.url,
            cb_kwargs={"item": item, "attempts": attempts + 1},
            callback=self.parse_html_report,
            dont_filter=True,
        )


class IncrementalFilings(SrNumSpiderMixin, LM30):
    """Crawl filings for a specific list of filers (by srFilerId).
    Inputs come from scripts/discover_new_filings.py, which
    forward-probes the rptId space to find new filings since the last
    sync."""

    name = "filings_incremental"


class LM30Report:
    """Parse the Part A/B/C disclosure blocks out of an LM-30 report
    (orgReport.do). The Revised-2011 markup is a YUI3 grid: each part is
    a sequence of `rpt-box box-top-only` entry blocks (or a
    `rpt-no_data-box` when nil); within an entry, labels and their values
    are sibling cells in a `yui3-g` row (the value carries an `rpt-data`
    class). Revisions other than 2011 are not yet handled."""

    @classmethod
    def parse(cls, response):
        return {
            "part_a": cls._part_a(response),
            "part_b": cls._part_b(response),
            "part_c": cls._part_c(response),
        }

    @classmethod
    def _part_a(cls, response):
        out = []
        for entry in cls._entries(response, "PART A"):
            row_data = {}
            for row in cls._rows(entry):
                for label, key in (
                    ("6. Name of represented employer", "represented_employer"),
                    (
                        "7.a. Nature of interest, transaction, benefit, "
                        "arrangement, income, or loan.",
                        "nature_of_interest",
                    ),
                    (
                        "7.b. Amount or value of interest, transaction, "
                        "benefit, arrangement, income, or loan.",
                        "amount",
                    ),
                ):
                    cls._set(row_data, row, label, key)
                for label, key in IDENTITY.items():
                    cls._set(row_data, row, label, key)
            out.append(row_data)
        return out

    @classmethod
    def _part_b(cls, response):
        out = []
        for entry in cls._entries(response, "PART B"):
            row_data = {}
            section = "business"
            for row in cls._rows(entry):
                norm = cls._norm(row)
                if norm.startswith("10. If 9.b or 9.c"):
                    section = "deals_with"
                    continue
                if norm.startswith("9. Business deals with"):
                    deals = cls._deals_with(row)
                    if deals:
                        row_data["deals_with"] = deals
                    continue
                for label, key in (
                    ("8. Name of business", "business_name"),
                    (
                        "Name of employer or labor relations consultant",
                        "deals_with_name",
                    ),
                    ("11.a. Nature of dealings", "nature_of_dealings"),
                    ("11.b. Value of dealings", "value_of_dealings"),
                    (
                        "12.a. Nature of interest, benefit, arrangement, or income",
                        "nature_of_interest",
                    ),
                    (
                        "12.b. Amount or value of interest, benefit, "
                        "arrangement, or income",
                        "amount_of_interest",
                    ),
                ):
                    cls._set(row_data, row, label, key)
                for label, key in IDENTITY.items():
                    prefix = "" if section == "business" else "deals_with_"
                    cls._set(row_data, row, label, prefix + key)
            out.append(row_data)
        return out

    @classmethod
    def _part_c(cls, response):
        # MODELED, NOT YET VALIDATED against a real populated Part C (they
        # are rare). The Makefile/update.mk tripwire asserts part_c is
        # empty, so the first real one fails the build loudly with an
        # rptId to validate these labels against. See PR notes.
        out = []
        for entry in cls._entries(response, "PART C"):
            row_data = {}
            for row in cls._rows(entry):
                for label, key in (
                    ("13. Name of employer", "other_employer"),
                    (
                        "14.a. Nature of interest, transaction, benefit, "
                        "arrangement, income, or loan.",
                        "nature_of_interest",
                    ),
                    (
                        "14.b. Amount or value of interest, transaction, "
                        "benefit, arrangement, income, or loan.",
                        "amount",
                    ),
                ):
                    cls._set(row_data, row, label, key)
                for label, key in IDENTITY.items():
                    cls._set(row_data, row, label, key)
            out.append(row_data)
        return out

    # -- helpers ------------------------------------------------------

    @staticmethod
    def _entries(response, marker):
        return response.xpath(
            "//div[contains(@class,'rpt-box') and contains(@class,'box-top-only')]"
            "[preceding::span[contains(@class,'rpt-part-name')][1]"
            "[contains(., $marker)]]",
            marker=marker,
        )

    @staticmethod
    def _rows(entry):
        return entry.xpath(".//div[contains(@class,'rpt-instruction-box')]")

    @staticmethod
    def _norm(row):
        return " ".join(" ".join(row.xpath(".//text()").getall()).split())

    @staticmethod
    def _value(row, label):
        return (
            row.xpath(
                ".//div[normalize-space(.)=$label]"
                "/following-sibling::div[contains(@class,'rpt-data')][1]//text()",
                label=label,
            )
            .get(default="")
            .strip()
        )

    @classmethod
    def _set(cls, row_data, row, label, key):
        value = cls._value(row, label)
        if value:
            row_data[key] = value

    @staticmethod
    def _deals_with(row):
        checked = []
        for label, key in (
            ("a. Labor Organization", "labor_organization"),
            ("b. Trust", "trust"),
            ("c. Employer", "employer"),
        ):
            box = row.xpath(
                ".//div[contains(normalize-space(.), $label)]"
                "/preceding-sibling::div[1]//input[@checked]",
                label=label,
            )
            if box:
                checked.append(key)
        return ",".join(checked)
