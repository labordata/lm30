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


def test_header_filer_and_union_identity():
    h = LM30Report.parse(_report("942003.html"))["header"][0]
    assert h["filer_name"] == "William T Mullen"
    assert h["filer_street"] == "77 BRANT AVE SUITE 102,"
    assert h["filer_city"] == "Clark"
    assert h["filer_state"] == "NJ"
    assert h["filer_zip"] == "07066"
    assert h["filer_email"] == "njbctc@njbctc.org"
    assert h["filer_role"] == "Officer"
    assert h["filer_position_title"] == "President"
    assert h["union_name"] == "BLDG AND CONSTRN TRADES DEPT AFL-CIO"
    assert h["union_file_number"] == "049-389"
    assert h["union_state"] == "NJ"


def test_header_employee_role_and_title():
    h = LM30Report.parse(_report("941060.html"))["header"][0]
    assert h["filer_role"] == "Employee"
    assert h["filer_position_title"] == "Chief Legal Officer, THINK450"
    assert h["union_file_number"] == "068-015"


def test_header_shape_mismatch_raises_loudly():
    import re

    from lm30.spiders.filings import HeaderShapeError

    html = (FIXTURES / "942003.html").read_text()
    # simulate OLMS renaming a header label (markup drift)
    mangled = html.replace("Email address (optional)", "E-mail")
    resp = HtmlResponse(url="x", body=mangled.encode(), encoding="utf-8")
    try:
        LM30Report.parse(resp)
        assert False, "expected HeaderShapeError"
    except HeaderShapeError as exc:
        assert "item 4" in str(exc)
        assert "E-mail" in str(exc) or "Email" in str(exc)
