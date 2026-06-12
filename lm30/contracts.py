from olms.contracts import FormContract


class FilersFormContract(FormContract):
    name = "filers_form"
    formdata = {"clearCache": "F", "page": "1"}


class FilingsFormContract(FormContract):
    name = "filings_form"
    formdata = {"srFilerId": "105563"}


class AmendmentsFormContract(FormContract):
    name = "amendments_form"
    formdata = {"srFilerId": "106017", "yrCovered": "2004"}
