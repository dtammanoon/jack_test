
import frappe
from frappe import _

from erpnext.accounts.doctype.pos_invoice.pos_invoice import POSInvoice


class CustomPOSInvoice(POSInvoice):
    def check_zero_rate(self):
        """Avoid false zero-rate warning from POS Invoice incoming_rate.

        Keep the valuation_rate check intact.
        This does not modify stock valuation or stock ledger entries.
        """

        for item in self.get("items"):
            if (
                item.get("valuation_rate") == 0
                and item.get("allow_zero_valuation_rate") == 0
                and frappe.get_cached_value(
                    "Item", item.item_code, "is_stock_item"
                )
            ):
                frappe.toast(
                    _(
                        "Row #{0}: Item {1} has zero rate but '{2}' is not enabled."
                    ).format(
                        item.idx,
                        frappe.bold(item.item_code),
                        item.meta.get_label("allow_zero_valuation_rate"),
                    ),
                    indicator="orange",
                )
