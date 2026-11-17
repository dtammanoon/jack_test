
import frappe


def add_pos_full_tax_invoice(bootinfo):
    """Add POS Full Tax Invoice and its Query Report to Selling sidebar."""

    module_sidebars = bootinfo.get("module_sidebars") or {}
    selling = module_sidebars.get("Selling")

    if not selling:
        return

    items = selling.get("items") or []

    # ---------------------------------------------------------
    # 1. Add POS Full Tax Invoice DocType
    # ---------------------------------------------------------

    doctype_name = "POS Full Tax Invoice"

    if (
        frappe.db.exists("DocType", doctype_name)
        and frappe.has_permission(doctype_name, ptype="read")
    ):

        # Remove duplicate custom DocType entry
        items[:] = [
            item
            for item in items
            if not (
                item.get("type") == "Link"
                and item.get("link_type") == "DocType"
                and item.get("link_to") == doctype_name
            )
        ]

        # Locate POS Invoice
        pos_invoice_index = next(
            (
                index
                for index, item in enumerate(items)
                if item.get("type") == "Link"
                and item.get("link_type") == "DocType"
                and item.get("link_to") == "POS Invoice"
            ),
            None,
        )

        if pos_invoice_index is not None:
            doctype_item = {
                "child": 1,
                "collapsible": 1,
                "filters": None,
                "icon": None,
                "indent": 0,
                "is_default_module": 0,
                "keep_closed": 0,
                "key": "Link|DocType|POS Full Tax Invoice||",
                "label": "POS Full Tax Invoice",
                "link_to": doctype_name,
                "link_type": "DocType",
                "open_in_new_tab": 0,
                "route_options": None,
                "show_arrow": 0,
                "tab": None,
                "type": "Link",
                "url": None,
            }

            items.insert(pos_invoice_index + 1, doctype_item)

    # ---------------------------------------------------------
    # 2. Add POS Full Tax Invoice Report
    # ---------------------------------------------------------

    report_name = "POS Full Tax Invoice"

    # Remove previous injected Report entry to prevent duplicates
    items[:] = [
        item
        for item in items
        if not (
            item.get("type") == "Link"
            and item.get("link_type") == "Report"
            and item.get("link_to") == report_name
        )
    ]

    report = frappe.db.get_value(
        "Report",
        report_name,
        ["report_type", "ref_doctype", "disabled"],
        as_dict=True,
    )

    if not report or report.disabled:
        return

    # Use the same allowed-report list as Frappe 16
    from frappe.desk.desk_views import DeskViews

    allowed_reports = DeskViews().allowed_reports or {}

    if report_name not in allowed_reports:
        return

    # Locate the existing DocType link
    doctype_index = next(
        (
            index
            for index, item in enumerate(items)
            if item.get("type") == "Link"
            and item.get("link_type") == "DocType"
            and item.get("link_to") == doctype_name
        ),
        None,
    )

    if doctype_index is None:
        return

    report_item = {
        "child": 1,
        "collapsible": 1,
        "filters": None,
        "icon": None,
        "indent": 0,
        "is_default_module": 0,
        "keep_closed": 0,
        "key": "Link|Report|POS Full Tax Invoice||",
        "label": "POS Full Tax Invoice Report",
        "link_to": report_name,
        "link_type": "Report",
        "open_in_new_tab": 0,
        "route_options": None,
        "show_arrow": 0,
        "tab": None,
        "type": "Link",
        "url": None,
        "report": {
            "report_type": report.report_type,
            "ref_doctype": report.ref_doctype,
        },
    }

    items.insert(doctype_index + 1, report_item)
