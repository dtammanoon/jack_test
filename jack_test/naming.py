import frappe
from frappe.utils import getdate, nowdate

def parse_doc_date(doc, variable):
    d = getdate(
        (doc and (doc.get("posting_date") or doc.get("transaction_date"))) or nowdate()
    )
    return {
        "DOCYYYY": d.strftime("%Y"),
        "DOCYY": d.strftime("%y"),
        "DOCMM": d.strftime("%m"),
    }[variable]