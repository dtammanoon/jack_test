
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime


class POSFullTaxInvoice(Document):

    def validate(self):
        previous = self.get_doc_before_save()

        if previous and previous.pos_invoice != self.pos_invoice:
            self.buyer_name = None
            self.buyer_tax_id = None
            self.buyer_address = None

        self.validate_original_pos_invoice()
        self.capture_original_snapshot()
        self.capture_closing_entry()
        self.validate_replacement()
        self.validate_duplicate_pos_invoice()

    def get_original_pos_invoice(self):
        if not self.pos_invoice:
            frappe.throw(_("Original POS Invoice is required."))

        if not frappe.db.exists("POS Invoice", self.pos_invoice):
            frappe.throw(
                _("POS Invoice {0} does not exist.").format(self.pos_invoice)
            )

        return frappe.get_doc("POS Invoice", self.pos_invoice)

    def validate_original_pos_invoice(self):
        pos = self.get_original_pos_invoice()

        if pos.docstatus != 1:
            frappe.throw(_("Original POS Invoice must be submitted."))

        if pos.is_return:
            frappe.throw(
                _("Return POS Invoice cannot be used for a Full Tax Invoice.")
            )

        if not pos.pos_profile:
            frappe.throw(
                _("POS Profile is missing in the original POS Invoice.")
            )

        self.company = pos.company

    def capture_original_snapshot(self):
        if not self.pos_invoice:
            return

        pos = self.get_original_pos_invoice()

        self.company = pos.company
        self.pos_profile = pos.pos_profile

        self.pos_invoice_number = pos.name
        self.pos_posting_date = pos.posting_date
        self.pos_posting_time = pos.posting_time

        # Full Tax Invoice Date follows the original POS Invoice date.
        self.full_tax_invoice_date = pos.posting_date

        self.customer = pos.customer
        self.original_customer_name = pos.customer_name
        self.original_tax_id = pos.tax_id
        self.pos_customer_address = pos.customer_address

        # Reference only. This is NOT a replacement Sales Invoice.
        self.pos_consolidated_invoice = pos.consolidated_invoice

        self.original_net_total = pos.net_total or 0
        self.original_vat_amount = pos.total_taxes_and_charges or 0
        self.original_grand_total = pos.grand_total or 0
        self.original_paid_amount = pos.paid_amount or 0

        # Preserve manually corrected buyer information.
        if not self.buyer_name:
            self.buyer_name = pos.customer_name or pos.customer

        if not self.buyer_tax_id:
            self.buyer_tax_id = pos.tax_id

        if not self.buyer_address:
            self.buyer_address = pos.address_display

    def capture_closing_entry(self):
        if not self.pos_invoice:
            return

        closing_entry = frappe.db.get_value(
            "POS Invoice Reference",
            {
                "pos_invoice": self.pos_invoice,
                "parenttype": "POS Closing Entry",
                "docstatus": 1
            },
            "parent"
        )

        if closing_entry:
            self.pos_closing_entry = closing_entry

    def validate_replacement(self):
        if not self.replacement_of:
            # If an earlier document was cancelled, require an audit link.
            previous_cancelled = frappe.db.get_value(
                "POS Full Tax Invoice",
                {
                    "pos_invoice": self.pos_invoice,
                    "docstatus": 2
                },
                "name",
                order_by="modified desc"
            )

            if previous_cancelled:
                frappe.throw(
                    _(
                        "This POS Invoice has a cancelled Full Tax Invoice "
                        "({0}). Select it in Replacement Of."
                    ).format(previous_cancelled)
                )
            return

        if self.replacement_of == self.name:
            frappe.throw(_("A document cannot replace itself."))

        old_doc = frappe.get_doc(
            "POS Full Tax Invoice",
            self.replacement_of
        )

        if old_doc.docstatus != 2:
            frappe.throw(
                _("Replacement Of must refer to a cancelled document.")
            )

        if old_doc.pos_invoice != self.pos_invoice:
            frappe.throw(
                _("Replacement document must use the same original POS Invoice.")
            )


    def validate_duplicate_pos_invoice(self):
        if not self.pos_invoice:
            return

        existing = frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Full Tax Invoice`
            WHERE pos_invoice = %s
              AND docstatus < 2
              AND name != %s
            LIMIT 1
            FOR UPDATE
            """,
            (self.pos_invoice, self.name or ""),
            as_dict=True
        )

        if existing:
            frappe.throw(
                _(
                    "POS Invoice {0} already has an active Full Tax Invoice "
                    "document: {1}"
                ).format(self.pos_invoice, existing[0].name)
            )


    def get_profile_series(self):
        if not self.pos_profile:
            frappe.throw(_("POS Profile is required."))

        series = frappe.db.get_value(
            "POS Profile",
            self.pos_profile,
            "custom_full_tax_invoice_series"
        )

        if not series:
            frappe.throw(
                _(
                    "Please configure Full Tax Invoice Series in POS Profile {0}."
                ).format(self.pos_profile)
            )

        if "#####" not in series:
            frappe.throw(
                _(
                    "Invalid Full Tax Invoice Series in POS Profile {0}. "
                    "The pattern must contain a numeric placeholder such as #####."
                ).format(self.pos_profile)
            )

        return series

    def before_submit(self):
        # Lock the original POS Invoice row.
        # This serializes simultaneous submissions for the same POS Invoice.
        frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Invoice`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.pos_invoice,)
        )

        # Re-check source document after acquiring the lock.
        pos = self.get_original_pos_invoice()

        if pos.docstatus != 1 or pos.is_return:
            frappe.throw(
                _("Original POS Invoice is no longer eligible for a Full Tax Invoice.")
            )

        if pos.pos_profile != self.pos_profile:
            frappe.throw(
                _("POS Profile does not match the original POS Invoice.")
            )

        # Check duplicates again while holding the source-row lock.
        self.validate_duplicate_pos_invoice()

        if self.full_tax_invoice_number:
            frappe.throw(
                _("Full Tax Invoice Number must not be entered manually.")
            )

        series = self.get_profile_series()

        # YYYY is intentionally based on the system date at issuance time.
        # Frappe's Series table handles sequential numbering with row locking.
        self.full_tax_invoice_number = make_autoname(series)

        self.issued_on = now_datetime()
        self.issued_by = frappe.session.user
