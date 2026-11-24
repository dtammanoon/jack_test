import frappe
from frappe.contacts.doctype.address.address import get_address_display


def set_company_address_from_branch(doc, method=None):
    """ตั้ง company_address ตาม Branch Address ของ branch ในเอกสาร"""
    if doc.docstatus != 0 or not doc.get("branch"):
        return
    if not doc.meta.has_field("company_address"):
        return

    addr = frappe.db.get_value("Branch Address", {"branch": doc.branch}, "billing_address")
    if not addr:
        return

    if doc.company_address != addr:
        doc.company_address = addr
        if doc.meta.has_field("company_address_display"):
            doc.company_address_display = get_address_display(addr)