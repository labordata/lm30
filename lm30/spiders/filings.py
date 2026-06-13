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

# Part C labels its address "Mailing Address" rather than "Street Address".
PART_C_IDENTITY = dict(IDENTITY, **{"Mailing Address": "street"})
del PART_C_IDENTITY["Street Address"]


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
            try:
                item["detailed_form_data"] = LM30Report.parse(response)
            except HeaderShapeError as exc:
                # the markup drifted or a non-2011 revision slipped the
                # rpt-part-name filter — surface it loudly (a local
                # scrape sees every occurrence) but keep the filing's
                # index row rather than failing the whole crawl
                self.logger.error(
                    "report header shape mismatch for rptId %s (%s): %s",
                    item["rptId"],
                    response.request.url,
                    exc,
                )
                self.crawler.stats.inc_value("lm30/header_shape_mismatch")
                item["detailed_form_data"] = None
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


class HeaderShapeError(Exception):
    """The report header's label layout differs from the Revised-2011
    shape the parser was written against. Raised so a local scrape
    surfaces the variant loudly instead of silently emitting nulls."""


class LM30Report:
    """Parse the Part A/B/C disclosure blocks out of an LM-30 report
    (orgReport.do). The Revised-2011 markup is a YUI3 grid: each part is
    a sequence of `rpt-box box-top-only` entry blocks (or a
    `rpt-no_data-box` when nil); within an entry, labels and their values
    are sibling cells in a `yui3-g` row (the value carries an `rpt-data`
    class). Revisions other than 2011 are not yet handled."""

    @classmethod
    def parse(cls, response):
        # header is a 0-or-1-element list so the loader's flatten spec
        # makes one report_identity row per filing (or none).
        return {
            "header": [cls._header(response)],
            "part_a": cls._part_a(response),
            "part_b": cls._part_b(response),
            "part_c": cls._part_c(response),
        }

    # -- report header (items 4 & 5) ----------------------------------

    # The label-box texts the parser was written against, asserted on
    # every report. A surprise (missing or extra label) means the markup
    # drifted or a non-2011 revision slipped through the spider's filter;
    # raising surfaces it loudly on a local scrape instead of silently
    # emitting nulls.
    FILER_LABELS = frozenset(
        {
            "Name (first, middle, last)",
            "Street address",
            "City State ZIP",
            "Email address (optional)",
        }
    )
    UNION_LABELS = frozenset(
        {
            "Name",
            "Street address",
            "City State ZIP",
            "File number",
            "Officer Employee",
            "Your officer position or job title",
        }
    )

    @classmethod
    def _header(cls, response):
        filer = response.xpath(
            "//div[contains(@class,'rpt-instruction')]"
            "[contains(., '4. Your Contact Information')]/parent::div"
        )
        union = response.xpath("//div[@id='fistUnion']")
        if not filer or not union:
            raise HeaderShapeError(
                f"missing header section (filer={bool(filer)},"
                f" union={bool(union)})"
            )
        cls._check_labels(filer, cls.FILER_LABELS, "item 4 (filer)")
        cls._check_labels(union, cls.UNION_LABELS, "item 5 (labor org)")

        fcity, fstate, fzip = cls._csz(filer)
        ucity, ustate, uzip = cls._csz(union)
        return {
            "filer_name": cls._labeled(filer, "Name (first"),
            "filer_street": cls._street(filer),
            "filer_city": fcity,
            "filer_state": fstate,
            "filer_zip": fzip,
            "filer_email": cls._labeled(filer, "Email address"),
            "union_name": cls._labeled(union, "Name"),
            "union_street": cls._street(union),
            "union_city": ucity,
            "union_state": ustate,
            "union_zip": uzip,
            "union_file_number": cls._labeled(union, "File number"),
            "filer_role": cls._role(union),
            "filer_position_title": cls._labeled(
                union, "officer position or job title"
            ),
        }

    @staticmethod
    def _check_labels(scope, expected, where):
        seen = set()
        for box in scope.xpath(
            ".//div[contains(@class,'rpt-instruction-box')]"
        ):
            label = " ".join(
                " ".join(
                    box.xpath(
                        ".//text()[not(ancestor::*[contains(@class,'rpt-data')])]"
                    ).getall()
                ).split()
            )
            if label:
                seen.add(label)
        missing = expected - seen
        extra = seen - expected
        if missing or extra:
            raise HeaderShapeError(
                f"{where} label mismatch: missing={sorted(missing)},"
                f" unexpected={sorted(extra)}"
            )

    @staticmethod
    def _labeled(scope, contains):
        return (
            scope.xpath(
                ".//div[contains(@class,'rpt-instruction-box')][contains(., $c)]"
                "//*[contains(@class,'rpt-data')][1]//text()",
                c=contains,
            )
            .get(default="")
            .strip()
        ) or None

    @staticmethod
    def _street(scope):
        return (
            scope.xpath(
                ".//div[contains(@class,'rpt-instruction-box')]"
                "[contains(., 'Street address')]"
                "//*[contains(@class,'rpt-data')][1]//text()",
            )
            .get(default="")
            .strip()
        ) or None

    @staticmethod
    def _csz(scope):
        spans = [
            s.strip()
            for s in scope.xpath(
                ".//div[contains(@class,'rpt-instruction-box')]"
                "[contains(., 'City') and contains(., 'State')"
                " and contains(., 'ZIP')]"
                "//span[contains(@class,'rpt-data')]/text()"
            ).getall()
        ]
        return (spans + [None, None, None])[:3]

    @staticmethod
    def _role(union):
        for role in ("Officer", "Employee"):
            if union.xpath(
                ".//div[normalize-space(text())=$r]"
                "/following-sibling::div[1]//input[@checked]",
                r=role,
            ):
                return role
        return None

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
        out = []
        for entry in cls._entries(response, "PART C"):
            row_data = {}
            for row in cls._rows(entry):
                if cls._norm(row).startswith("13.b. Type of entity"):
                    entity = cls._entity_type(row)
                    if entity:
                        row_data["entity_type"] = entity
                    continue
                for label, key in (
                    (
                        "Name of employer or labor relations consultant",
                        "other_employer",
                    ),
                    ("14.a. Nature of payment", "nature_of_payment"),
                    ("14.b. Amount or value of payment", "amount"),
                ):
                    cls._set(row_data, row, label, key)
                for label, key in PART_C_IDENTITY.items():
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

    @staticmethod
    def _entity_type(row):
        # Part C item 13.b: a checkbox precedes each label, one checked.
        for label, key in (("an employer or", "employer"), ("a consultant?", "consultant")):
            box = row.xpath(
                ".//div[contains(normalize-space(.), $label)]"
                "/preceding-sibling::div[1]//input[@checked]",
                label=label,
            )
            if box:
                return key
        return ""
