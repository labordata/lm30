from scrapy import Spider

from olms.http import form_request


class LM30Filers(Spider):
    """One row per LM-30 filer (a union officer or employee, with the
    union they reported against)."""

    name = "filers"

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
        @returns items 500
        @returns requests 1 1
        """
        data = response.json()
        filers = data["filerList"]
        self.logger.info(
            f"Page {page}: got {len(filers)} filers"
            f" ({seen + len(filers)}/{data['totalRecords']})"
        )
        yield from filers

        # page sizes are irregular (500, then thousands); page until
        # we've seen totalRecords
        seen += len(filers)
        if filers and seen < data["totalRecords"]:
            page += 1
            yield form_request(
                "https://olmsapps.dol.gov/olpdr/GetLM30FilerListServlet",
                formdata={"clearCache": "F", "page": str(page)},
                cb_kwargs={"page": page, "seen": seen},
                callback=self.parse,
            )
