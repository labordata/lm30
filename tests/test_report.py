from pathlib import Path

from scrapy.http import HtmlResponse

from lm30.spiders.filings import LM30Report

FIXTURES = Path(__file__).parent / "fixtures"


def _report(name):
    return HtmlResponse(
        url="https://olmsapps.dol.gov/query/orgReport.do",
        body=(FIXTURES / name).read_bytes(),
        encoding="utf-8",
    )


def test_part_a_represented_employer():
    data = LM30Report.parse(_report("941060.html"))
    (a,) = data["part_a"]
    assert a["represented_employer"] == "NATIONAL BASKETBALL ASSOCIATION"
    assert a["city"] == "NEW YORK"
    assert a["state"] == "NY"
    assert a["nature_of_interest"] == "N/A"
    assert a["amount"] == "$0"


def test_part_b_multiple_businesses_and_deals_with():
    data = LM30Report.parse(_report("941060.html"))
    b = data["part_b"]
    assert {row["business_name"] for row in b} == {
        "NIKE, Inc.",
        "Patterson Belknap Webb & Tyler LLP",
    }
    nike = next(r for r in b if r["business_name"].startswith("NIKE"))
    assert nike["deals_with"] == "labor_organization"
    assert nike["amount_of_interest"] == "$162,262"
    # item 10 is empty when 9.a (labor organization) is checked
    assert "deals_with_name" not in nike


def test_part_b_item_10_subblock_namespaced():
    # 9.b (trust) checked -> item 10 sub-block populated and kept distinct
    # from the business identity even when they coincide.
    data = LM30Report.parse(_report("942119.html"))
    assert data["part_a"] == []
    first = data["part_b"][0]
    assert first["business_name"] == "Michigan Education Special Services Associati"
    assert first["deals_with"] == "trust"
    assert first["deals_with_name"] == "Michigan Education Special Services Associati"
    assert first["deals_with_city"] == "East Lansing"
    assert first["amount_of_interest"] == "$2,591"


def test_nil_part_is_empty_list():
    # 941871 has only Part B; A and C are nil.
    data = LM30Report.parse(_report("941871.html"))
    assert data["part_a"] == []
    assert data["part_c"] == []
    assert data["part_b"]


def test_part_c_other_employer():
    # Part C uses "Mailing Address" (not "Street Address"), the item-13.b
    # employer/consultant checkbox, and "14.a/b ... payment" labels.
    data = LM30Report.parse(_report("942003.html"))
    (c,) = data["part_c"]
    assert c["other_employer"] == "PSE&G"
    assert c["street"] == "80 Park Plaza,"
    assert c["city"] == "NEWARK"
    assert c["entity_type"] == "employer"
    assert c["nature_of_payment"] == "Football tickets and meals"
    assert c["amount"] == "$1,274"


def test_part_c_absent_when_nil():
    # Part-A/B-only filings leave Part C empty.
    for name in ("941060.html", "942119.html", "941871.html"):
        assert LM30Report.parse(_report(name))["part_c"] == []
