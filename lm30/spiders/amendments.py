from scrapy import Spider

from olms.http import form_request


class Amendments(Spider):
    """Full amendment chains, including the superseded versions the filer
    detail feed hides.

    An LM-30 amendment gets a new rptId; GetLM30FilerDetailServlet serves
    only the latest version of each (srFilerId, yrCovered) chain, so the
    earlier versions never reach the filing table.
    GetLM30AmendmentReportsServlet returns the whole chain. The chains to
    backfill — those with amended='Y' — come from the filing table via
    scripts/amended_chains.py, passed as `-a chains_file=...` (one
    "srFilerId,yrCovered" per line)."""

    name = "amendments"

    custom_settings = {
        "ITEM_PIPELINES": {
            "olms.pipelines.TimestampToDatetime": 1,
        }
    }

    def __init__(self, chains_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not chains_file:
            raise ValueError(
                "pass -a chains_file=/path/to/file (lines: srFilerId,yrCovered)"
            )
        self.chains = []
        with open(chains_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    sr_filer_id, yr_covered = line.split(",")
                    self.chains.append((sr_filer_id.strip(), yr_covered.strip()))

    async def start(self):
        for sr_filer_id, yr_covered in self.chains:
            yield form_request(
                "https://olmsapps.dol.gov/olpdr/GetLM30AmendmentReportsServlet",
                formdata={"srFilerId": sr_filer_id, "yrCovered": yr_covered},
                callback=self.parse,
            )

    def parse(self, response):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM30AmendmentReportsServlet
        @amendments_form
        @returns items 1
        """
        for version in response.json()["detail"]:
            # the amendment feed names the filer fNum; the rest of the
            # pipeline keys filers by srFilerId
            version["srFilerId"] = version.pop("fNum")
            # the amendment feed omits registerDate that the shared
            # TimestampToDatetime pipeline expects; it is --ignore'd on merge
            version.setdefault("registerDate", None)
            version["filing_url"] = (
                "https://olmsapps.dol.gov/query/orgReport.do"
                "?rptId={rptId}&rptForm={formLink}".format(**version)
            )
            yield version
