from scrapy import Spider

from olms.http import form_request
from olms.spiders import SrNumSpiderMixin


class LM30(Spider):
    """One row per LM-30 filing, from each filer's detail feed.

    The detail rows are flat — there is no nested form fan-out like the
    sibling pipelines — so the feed is the dataset. Documents are not
    archived (yet): filing_url points at the report."""

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
            yield filing


class IncrementalFilings(SrNumSpiderMixin, LM30):
    """Crawl filings for a specific list of filers (by srFilerId).
    Inputs come from scripts/discover_new_filings.py, which
    forward-probes the rptId space to find new filings since the last
    sync."""

    name = "filings_incremental"
