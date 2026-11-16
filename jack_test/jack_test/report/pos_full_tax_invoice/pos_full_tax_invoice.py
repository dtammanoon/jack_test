import frappe
from frappe import _


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = [
        {
            "fieldname": "name",
            "label": _("Tracking ID"),
            "fieldtype": "Link",
            "options": "POS Full Tax Invoice",
            "width": 155
        },
        {
            "fieldname": "docstatus",
            "label": _("Document Status"),
            "fieldtype": "Data",
            "width": 110
        },
        {
            "fieldname": "pos_invoice",
            "label": _("Original POS Invoice"),
            "fieldtype": "Link",
            "options": "POS Invoice",
            "width": 165
        },
        {
            "fieldname": "pos_profile",
            "label": _("POS Profile"),
            "fieldtype": "Link",
            "options": "POS Profile",
            "width": 160
        },
        {
            "fieldname": "pos_posting_date",
            "label": _("POS Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 140
        },
        {
            "fieldname": "original_customer_name",
            "label": _("Original Customer Name"),
            "fieldtype": "Data",
            "width": 170
        },
        {
            "fieldname": "original_vat_amount",
            "label": _("Original VAT"),
            "fieldtype": "Currency",
            "width": 115
        },
        {
            "fieldname": "original_grand_total",
            "label": _("Original Total"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "full_tax_invoice_number",
            "label": _("Full Tax Invoice Number"),
            "fieldtype": "Data",
            "width": 175
        },
        {
            "fieldname": "full_tax_invoice_date",
            "label": _("Full Tax Invoice Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "issued_on",
            "label": _("Issued On"),
            "fieldtype": "Datetime",
            "width": 150
        },
        {
            "fieldname": "pos_closing_entry",
            "label": _("POS Closing Entry"),
            "fieldtype": "Link",
            "options": "POS Closing Entry",
            "width": 160
        },
        {
            "fieldname": "pos_consolidated_invoice",
            "label": _("Consolidated Sales Invoice"),
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 170
        },
        {
            "fieldname": "replacement_of",
            "label": _("Replacement Of"),
            "fieldtype": "Link",
            "options": "POS Full Tax Invoice",
            "width": 160
        },
        {
            "fieldname": "issued_by",
            "label": _("Issued By"),
            "fieldtype": "Link",
            "options": "User",
            "width": 150
        }
    ]

    conditions = {}

    if filters.get("company"):
        conditions["company"] = filters.company

    if filters.get("customer"):
        conditions["customer"] = filters.customer

    if filters.get("pos_invoice"):
        conditions["pos_invoice"] = filters.pos_invoice

    if filters.get("pos_profile"):
        conditions["pos_profile"] = filters.pos_profile

    if filters.get("docstatus") not in (None, ""):
        conditions["docstatus"] = int(filters.docstatus)

    # Filter by the original POS Invoice date.
    if filters.get("pos_from_date") and filters.get("pos_to_date"):
        conditions["pos_posting_date"] = [
            "between",
            [filters.pos_from_date, filters.pos_to_date]
        ]
    elif filters.get("pos_from_date"):
        conditions["pos_posting_date"] = [
            ">=", filters.pos_from_date
        ]
    elif filters.get("pos_to_date"):
        conditions["pos_posting_date"] = [
            "<=", filters.pos_to_date
        ]

    # Filter by the actual date/time the full tax invoice was issued.
    if filters.get("issued_from_date") and filters.get("issued_to_date"):
        conditions["issued_on"] = [
            "between",
            [
                f"{filters.issued_from_date} 00:00:00",
                f"{filters.issued_to_date} 23:59:59"
            ]
        ]
    elif filters.get("issued_from_date"):
        conditions["issued_on"] = [
            ">=", f"{filters.issued_from_date} 00:00:00"
        ]
    elif filters.get("issued_to_date"):
        conditions["issued_on"] = [
            "<=", f"{filters.issued_to_date} 23:59:59"
        ]

    data = frappe.get_list(
        "POS Full Tax Invoice",
        filters=conditions,
        fields=[
            "name",
            "docstatus",
            "pos_invoice",
            "pos_profile",
            "pos_posting_date",
            "customer",
            "original_customer_name",
            "original_vat_amount",
            "original_grand_total",
            "full_tax_invoice_number",
            "full_tax_invoice_date",
            "issued_on",
            "pos_closing_entry",
            "pos_consolidated_invoice",
            "replacement_of",
            "issued_by"
        ],
        order_by="pos_posting_date desc, modified desc",
        limit_page_length=0
    )

    for row in data:
        row["docstatus"] = {
            0: _("Draft"),
            1: _("Submitted"),
            2: _("Cancelled")
        }.get(row.docstatus, row.docstatus)

    return columns, data
