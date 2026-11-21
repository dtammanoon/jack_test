import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, now_datetime, nowdate


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def buyer_customer_query(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters=None,
    as_dict=False,
    reference_doctype=None,
    ignore_user_permissions=False,
    link_fieldname=None,
):
    """Search Buyer Customer by normal fields and Customer/Address Tax ID."""

    doctype = "Customer"
    txt = (txt or "").strip()

    meta = frappe.get_meta(doctype)

    if isinstance(filters, dict):
        filters = filters.copy()
        include_disabled = filters.pop("include_disabled", 0) == 1
    elif filters is None:
        filters = {}
        include_disabled = False
    else:
        filters = list(filters)
        include_disabled = False

    if not include_disabled and meta.get_field("disabled"):
        if isinstance(filters, dict):
            filters["disabled"] = ["!=", 1]
        else:
            filters.append([doctype, "disabled", "!=", 1])

    searchable_types = {
        "Autocomplete",
        "Data",
        "Text",
        "Small Text",
        "Long Text",
        "Link",
        "Select",
        "Read Only",
        "Text Editor",
    }

    search_fields = ["name"]

    if meta.title_field:
        search_fields.append(meta.title_field)

    if meta.search_fields:
        search_fields.extend(meta.get_search_fields())

    or_filters = []
    seen_fields = set()

    if txt:
        for fieldname in search_fields:
            fieldname = fieldname.strip()

            if fieldname in seen_fields:
                continue

            seen_fields.add(fieldname)

            field = meta.get_field(fieldname)

            if fieldname == "name" or (
                field and field.fieldtype in searchable_types
            ):
                or_filters.append(
                    [fieldname, "like", f"%{txt}%"]
                )

        # Search Customer.tax_id directly.
        if meta.get_field("tax_id"):
            or_filters.append(
                ["tax_id", "like", f"%{txt}%"]
            )

        # Also search Tax ID from linked Addresses.
        address_tax_id_customers = frappe.db.sql(
            """
            SELECT DISTINCT dl.link_name
            FROM `tabDynamic Link` dl
            INNER JOIN `tabAddress` a
                ON a.name = dl.parent
            WHERE dl.parenttype = 'Address'
              AND dl.parentfield = 'links'
              AND dl.link_doctype = 'Customer'
              AND IFNULL(a.tax_id, '') != ''
              AND a.tax_id LIKE %s
            """,
            values=(f"%{txt}%",),
            pluck=True,
        )

        if address_tax_id_customers:
            or_filters.append(
                ["name", "in", address_tax_id_customers]
            )

    fields = ["name"]

    if meta.title_field and meta.title_field not in fields:
        fields.append(meta.title_field)

    if searchfield and searchfield not in fields:
        if meta.get_field(searchfield):
            fields.append(searchfield)

    if meta.search_fields:
        for fieldname in meta.get_search_fields():
            fieldname = fieldname.strip()

            if fieldname not in fields and meta.get_field(fieldname):
                fields.append(fieldname)

    return frappe.get_list(
        doctype,
        filters=filters,
        fields=fields,
        or_filters=or_filters,
        limit_start=start,
        limit_page_length=page_len,
        order_by="idx desc, name asc",
        ignore_user_permissions=ignore_user_permissions,
        reference_doctype=reference_doctype,
        as_list=not as_dict,
        strict=False,
    )



def get_pos_vat_details(pos_invoice):
    """
    Identify the VAT row using the POS Profile tax template.
    Read the actual calculated amount from the POS Invoice tax row.
    No account number, account name, company, or tax rate is hardcoded.
    """

    if not pos_invoice.pos_profile:
        frappe.throw(
            _("POS Invoice {0} has no POS Profile.").format(
                pos_invoice.name
            )
        )

    profile = frappe.get_doc("POS Profile", pos_invoice.pos_profile)
    template_name = profile.taxes_and_charges

    if not template_name:
        frappe.throw(
            _("POS Profile {0} has no Tax Template configured.").format(
                profile.name
            )
        )

    template = frappe.get_doc(
        "Sales Taxes and Charges Template",
        template_name,
    )

    def is_vat_description(value):
        value = (value or "").strip().lower()
        return "vat" in value or "ภาษีมูลค่าเพิ่ม" in value

    vat_template_rows = []

    for row in template.taxes:
        if is_vat_description(row.description):
            vat_template_rows.append(row)

    if len(vat_template_rows) != 1:
        frappe.throw(
            _(
                "Cannot identify exactly one VAT row in Tax Template "
                "{0}. Found {1} rows marked as VAT. "
                "Please review the tax row descriptions."
            ).format(template.name, len(vat_template_rows))
        )

    template_row = vat_template_rows[0]

    if template_row.is_tax_withholding_account:
        frappe.throw(
            _("The identified VAT row cannot be a withholding tax.")
        )

    matches = []

    for row in pos_invoice.taxes:
        if (
            row.account_head == template_row.account_head
            and row.charge_type == template_row.charge_type
            and flt(row.rate, 6) == flt(template_row.rate, 6)
            and (row.description or "").strip()
                == (template_row.description or "").strip()
        ):
            matches.append(row)

    if len(matches) != 1:
        frappe.throw(
            _(
                "Cannot match the VAT row in POS Invoice {0} "
                "with Tax Template {1}. Found {2} matching rows."
            ).format(
                pos_invoice.name,
                template.name,
                len(matches),
            )
        )

    actual_row = matches[0]

    if actual_row.is_tax_withholding_account:
        frappe.throw(
            _("The matched VAT row is configured as withholding tax.")
        )

    amount = actual_row.tax_amount_after_discount_amount

    if amount is None:
        amount = actual_row.tax_amount

    return {
        "amount": flt(amount, 2),
        "included_in_print_rate": int(
            actual_row.included_in_print_rate or 0
        ),
        "description": actual_row.description,
        "rate": flt(actual_row.rate, 6),
        "charge_type": actual_row.charge_type,
    }


class POSFullTaxInvoice(Document):

    def validate(self):
        if self.document_type == "Full Tax Credit Note":
            self.validate_credit_note_document()
            return

        previous = self.get_doc_before_save()

        # Changing the source POS Invoice resets the buyer selection.
        if previous and previous.pos_invoice != self.pos_invoice:
            self.buyer_customer = None
            self.buyer_customer_address = None
            self.clear_buyer_snapshot()

        self.validate_original_pos_invoice()
        self.capture_original_snapshot()
        self.capture_closing_entry()
        self.validate_buyer(previous)
        self.validate_replacement()

    def clear_buyer_snapshot(self):
        self.buyer_name = None
        self.buyer_tax_id = None
        self.buyer_branch = None
        self.buyer_address = None
        self.buyer_email = None

    def get_original_pos_invoice(self):
        if not self.pos_invoice:
            frappe.throw(_("Original POS Invoice is required."))

        if not frappe.db.exists("POS Invoice", self.pos_invoice):
            frappe.throw(
                _("POS Invoice {0} does not exist.").format(self.pos_invoice)
            )

        return frappe.get_doc("POS Invoice", self.pos_invoice)

    def get_branch_address(self, branch):
        if not branch:
            frappe.throw(
                _("Branch is missing in the original POS Invoice.")
            )

        if not frappe.db.exists("Branch Address", branch):
            frappe.throw(
                _("Please configure Branch Address for Branch {0}.").format(
                    branch
                )
            )

        branch_address = frappe.db.get_value(
            "Branch Address",
            branch,
            [
                "branch",
                "address",
                "billing_address",
                "full_tax_invoice_series",
                "credit_note_series",
            ],
            as_dict=True,
        )

        if not branch_address or branch_address.branch != branch:
            frappe.throw(
                _("Branch Address configuration is invalid for Branch {0}.").format(
                    branch
                )
            )

        if not branch_address.billing_address:
            frappe.throw(
                _("Issuer Billing Address is missing for Branch {0}.").format(
                    branch
                )
            )

        return branch_address

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

        branch_address = self.get_branch_address(pos.branch)

        self.company = pos.company
        self.branch = pos.branch
        self.branch_address = pos.branch
        self.billing_address = branch_address.billing_address

    def capture_original_snapshot(self):
        if not self.pos_invoice:
            return

        pos = self.get_original_pos_invoice()

        self.company = pos.company
        self.pos_profile = pos.pos_profile
        self.branch = pos.branch
        self.branch_address = pos.branch
        self.pos_invoice_number = pos.name
        self.pos_posting_date = pos.posting_date
        self.pos_posting_time = pos.posting_time
        self.full_tax_invoice_date = pos.posting_date
        self.customer = pos.customer
        self.original_customer_name = pos.customer_name
        self.original_tax_id = pos.tax_id
        self.pos_customer_address = pos.customer_address
        self.pos_consolidated_invoice = pos.consolidated_invoice
        self.original_net_total = pos.net_total or 0
        self.original_vat_amount = get_pos_vat_details(pos)["amount"]
        self.original_grand_total = pos.grand_total or 0
        self.original_paid_amount = pos.paid_amount or 0

        # Initialize Credit Note summary for a new Full Tax Invoice.
        self.credit_note_count = 0
        self.active_credit_note_count = 0

        self.total_returned_net = 0
        self.total_returned_vat = 0
        self.total_returned_grand_total = 0

        self.remaining_net = flt(self.original_net_total, 2)
        self.remaining_vat = flt(self.original_vat_amount, 2)
        self.remaining_grand_total = flt(self.original_grand_total, 2)

        # Default Buyer Customer to the original POS Invoice Customer.
        if not self.buyer_customer:
            self.buyer_customer = pos.customer

    def capture_closing_entry(self):
        if not self.pos_invoice:
            return

        closing_entry = frappe.db.get_value(
            "POS Invoice Reference",
            {
                "pos_invoice": self.pos_invoice,
                "parenttype": "POS Closing Entry",
                "docstatus": 1,
            },
            "parent",
        )

        if closing_entry:
            self.pos_closing_entry = closing_entry

    def get_default_buyer_address(self, customer):
        # Primary Address first; newest Address wins when priority is equal.
        result = frappe.db.sql(
            """
            SELECT a.name
            FROM `tabAddress` a
            INNER JOIN `tabDynamic Link` dl
                ON dl.parent = a.name
                AND dl.parenttype = 'Address'
                AND dl.link_doctype = 'Customer'
                AND dl.link_name = %s
            WHERE IFNULL(a.disabled, 0) = 0
            ORDER BY
                IFNULL(a.is_primary_address, 0) DESC,
                a.creation DESC
            LIMIT 1
            """,
            (customer,),
            as_dict=True,
        )

        return result[0].name if result else None

    def validate_buyer(self, previous=None, require_address=False):
        if not self.buyer_customer:
            if require_address:
                frappe.throw(_("Please select Buyer Customer."))
            return

        if not frappe.db.exists("Customer", self.buyer_customer):
            frappe.throw(
                _("Buyer Customer {0} does not exist.").format(
                    self.buyer_customer
                )
            )

        # Automatically select an eligible Address when none is selected.
        if not self.buyer_customer_address:
            self.buyer_customer_address = self.get_default_buyer_address(
                self.buyer_customer
            )

        if not self.buyer_customer_address:
            if require_address:
                frappe.throw(
                    _(
                        "No active Address is linked to Buyer Customer {0}. "
                        "Please create or link an Address before submitting."
                    ).format(self.buyer_customer)
                )

            # Keep the Customer's basic information available in Draft.
            customer = frappe.db.get_value(
                "Customer",
                self.buyer_customer,
                ["customer_name", "tax_id", "branch_code", "email_id"],
                as_dict=True,
            )

            buyer_changed = (
                not previous
                or previous.buyer_customer != self.buyer_customer
                or previous.buyer_customer_address
                != self.buyer_customer_address
            )

            if buyer_changed:
                self.buyer_name = customer.customer_name
                self.buyer_tax_id = customer.tax_id
                self.buyer_branch = customer.branch_code
                self.buyer_address = None
                self.buyer_email = customer.email_id

            return

        address_name = self.buyer_customer_address

        if not frappe.db.exists("Address", address_name):
            frappe.throw(
                _("Buyer Address {0} does not exist.").format(address_name)
            )

        address = frappe.get_doc("Address", address_name)

        if address.disabled:
            frappe.throw(_("Disabled Address cannot be used for a Full Tax Invoice."))

        linked = frappe.db.exists(
            "Dynamic Link",
            {
                "parent": address_name,
                "parenttype": "Address",
                "link_doctype": "Customer",
                "link_name": self.buyer_customer,
            },
        )

        if not linked:
            frappe.throw(
                _(
                    "Address {0} is not linked to Buyer Customer {1}."
                ).format(address_name, self.buyer_customer)
            )

        buyer_changed = (
            not previous
            or previous.buyer_customer != self.buyer_customer
            or previous.buyer_customer_address != self.buyer_customer_address
        )

        if buyer_changed:
            customer = frappe.db.get_value(
                "Customer",
                self.buyer_customer,
                ["customer_name", "tax_id", "branch_code", "email_id"],
                as_dict=True,
            )

            address_parts = [
                address.address_line1,
                address.address_line2,
                address.city,
                address.state,
                address.pincode,
                address.country,
            ]

            self.buyer_name = customer.customer_name
            self.buyer_tax_id = address.tax_id or customer.tax_id
            self.buyer_branch = address.branch_code or customer.branch_code
            self.buyer_address = " ".join(
                str(part).strip()
                for part in address_parts
                if part and str(part).strip()
            )
            self.buyer_email = address.email_id or customer.email_id

    def validate_replacement(self):
        # Replacement Of is optional.
        # A cancelled Full Tax Invoice does not prevent issuing a new one.
        if not self.replacement_of:
            return

        if self.replacement_of == self.name:
            frappe.throw(_("A document cannot replace itself."))

        old_doc = frappe.get_doc(
            "POS Full Tax Invoice", self.replacement_of
        )

        if old_doc.docstatus != 2:
            frappe.throw(
                _("Replacement Of must refer to a cancelled document.")
            )

        if old_doc.pos_invoice != self.pos_invoice:
            frappe.throw(
                _(
                    "Replacement document must use the same original "
                    "POS Invoice."
                )
            )

    def validate_duplicate_pos_invoice(self):
        if not self.pos_invoice:
            return

        existing = frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Full Tax Invoice`
            WHERE pos_invoice = %s
                AND docstatus = 1
                AND IFNULL(document_type, 'Full Tax Invoice') = 'Full Tax Invoice'
                AND name != %s
            LIMIT 1
            FOR UPDATE
            """,
            (self.pos_invoice, self.name or ""),
            as_dict=True,
        )

        if existing:
            frappe.throw(
                _(
                    "POS Invoice {0} already has an active Full Tax Invoice "
                    "document: {1}"
                ).format(self.pos_invoice, existing[0].name)
            )

    def get_branch_series(self):
        branch_address = self.get_branch_address(self.branch)
        series = branch_address.full_tax_invoice_series

        if not series:
            frappe.throw(
                _(
                    "Please configure Full Tax Invoice Series in "
                    "Branch Address {0}."
                ).format(self.branch_address)
            )

        if "#####" not in series:
            frappe.throw(
                _(
                    "Invalid Full Tax Invoice Series in Branch Address {0}. "
                    "The pattern must contain a numeric placeholder such as #####."
                ).format(self.branch_address)
            )

        return series

    def validate_credit_note_document(self):
        if not self.return_pos_invoice:
            frappe.throw(_("Return POS Invoice is required for a Credit Note."))

        if not self.original_full_tax_invoice:
            frappe.throw(_("Original Full Tax Invoice is required for a Credit Note."))

        return_pos = frappe.get_doc("POS Invoice", self.return_pos_invoice)

        if return_pos.docstatus != 1 or not return_pos.is_return:
            frappe.throw(_("Source Return POS Invoice must be submitted."))

        if not return_pos.return_against:
            frappe.throw(_("Return POS Invoice has no Original POS Invoice reference."))

        original_pos = frappe.get_doc("POS Invoice", return_pos.return_against)

        if original_pos.docstatus != 1 or original_pos.is_return:
            frappe.throw(
                _("Original POS Invoice must be submitted and must not be a Return.")
            )

        if self.pos_invoice and self.pos_invoice != original_pos.name:
            frappe.throw(_("Original POS Invoice does not match the Return POS Invoice."))

        original_tax_doc = frappe.get_doc(
            "POS Full Tax Invoice", self.original_full_tax_invoice
        )

        if (
            original_tax_doc.docstatus != 1
            or (original_tax_doc.document_type or "Full Tax Invoice") != "Full Tax Invoice"
            or original_tax_doc.pos_invoice != original_pos.name
        ):
            frappe.throw(
                _("Original Full Tax Invoice must be submitted and belong to the original POS Invoice.")
            )

        self.pos_invoice = original_pos.name

        # Copy the original Full Tax Invoice snapshot.
        # Credit Note items and taxes will be read from Return POS Invoice
        # by the Credit Note Print Format, not copied into child tables.
        snapshot_fields = [
            "pos_profile",
            "company",
            "branch",
            "branch_address",
            "billing_address",
            "pos_invoice_number",
            "pos_posting_date",
            "pos_posting_time",
            "full_tax_invoice_date",
            "full_tax_invoice_number",
            "customer",
            "original_customer_name",
            "original_tax_id",
            "pos_customer_address",
            "pos_consolidated_invoice",
            "pos_closing_entry",
            "original_net_total",
            "original_vat_amount",
            "original_grand_total",
            "original_paid_amount",
            "buyer_customer",
            "buyer_customer_address",
            "buyer_name",
            "buyer_tax_id",
            "buyer_branch",
            "buyer_address",
            "buyer_email",
            "remarks",
        ]

        for fieldname in snapshot_fields:
            self.set(fieldname, original_tax_doc.get(fieldname))

        # Calculate Credit Note Preview.
        # These values are provisional and will be recalculated
        # under database locks in before_submit_credit_note().
        preview_vat_details = get_pos_vat_details(return_pos)

        preview_current_net = abs(flt(return_pos.net_total, 2))
        preview_current_vat = abs(
            flt(preview_vat_details["amount"], 2)
        )
        preview_current_grand = abs(flt(return_pos.grand_total, 2))

        # Use the latest submitted Credit Note summary from the original.
        preview_previous_net = flt(
            original_tax_doc.total_returned_net, 2
        )
        preview_previous_vat = flt(
            original_tax_doc.total_returned_vat, 2
        )
        preview_previous_grand = flt(
            original_tax_doc.total_returned_grand_total, 2
        )

        preview_cumulative_net = flt(
            preview_previous_net + preview_current_net, 2
        )
        preview_cumulative_vat = flt(
            preview_previous_vat + preview_current_vat, 2
        )
        preview_cumulative_grand = flt(
            preview_previous_grand + preview_current_grand, 2
        )

        preview_remaining_net = flt(
            original_tax_doc.original_net_total
            - preview_cumulative_net,
            2,
        )
        preview_remaining_vat = flt(
            original_tax_doc.original_vat_amount
            - preview_cumulative_vat,
            2,
        )
        preview_remaining_grand = flt(
            original_tax_doc.original_grand_total
            - preview_cumulative_grand,
            2,
        )

        # Current Return amounts for Print Preview.
        self.current_return_net = preview_current_net
        self.current_return_vat = preview_current_vat
        self.current_return_grand_total = preview_current_grand

        # Cumulative amounts including this Draft as a preview.
        self.cumulative_returned_net = preview_cumulative_net
        self.cumulative_returned_vat = preview_cumulative_vat
        self.cumulative_returned_grand_total = preview_cumulative_grand

        # Remaining amounts after this Draft as a preview.
        self.remaining_net_after = max(preview_remaining_net, 0)
        self.remaining_vat_after = max(preview_remaining_vat, 0)
        self.remaining_grand_total_after = max(
            preview_remaining_grand, 0
        )

        # Prevent more than one active Draft for the same Return.
        duplicate_draft = frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Full Tax Invoice`
            WHERE return_pos_invoice = %s
                AND document_type = 'Full Tax Credit Note'
                AND docstatus = 0
                AND name != %s
            LIMIT 1
            """,
            (self.return_pos_invoice, self.name or ""),
            as_dict=True,
        )

        if duplicate_draft:
            frappe.throw(
                _("A Credit Note Draft already exists: {0}").format(
                    duplicate_draft[0].name
                )
            )

    def get_credit_note_series(self):
        branch_address = self.get_branch_address(self.branch)
        series = branch_address.credit_note_series

        if not series:
            frappe.throw(
                _("Please configure Credit Note Series in Branch Address {0}.").format(
                    self.branch_address
                )
            )

        if "#####" not in series:
            frappe.throw(
                _(
                    "Invalid Credit Note Series in Branch Address {0}. "
                    "The pattern must contain a numeric placeholder such as #####."
                ).format(self.branch_address)
            )

        return series

    def before_submit_credit_note(self):
        # Lock the original Full Tax Invoice first.
        frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Full Tax Invoice`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.original_full_tax_invoice,),
        )

        # Lock the Return POS Invoice second.
        frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Invoice`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.return_pos_invoice,),
        )

        self.validate_credit_note_document()

        if not (self.credit_note_reason or "").strip():
            frappe.throw(
                _("Please enter the Credit Note Reason before submitting.")
            )

        existing = frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Full Tax Invoice`
            WHERE return_pos_invoice = %s
                AND document_type = 'Full Tax Credit Note'
                AND docstatus = 1
                AND name != %s
            LIMIT 1
            """,
            (self.return_pos_invoice, self.name or ""),
            as_dict=True,
        )

        if existing:
            frappe.throw(
                _(
                    "Return POS Invoice {0} already has a submitted "
                    "Credit Note: {1}"
                ).format(self.return_pos_invoice, existing[0].name)
            )

        if self.credit_note_number:
            frappe.throw(
                _("Credit Note Number must not be entered manually.")
            )

        return_pos = frappe.get_doc(
            "POS Invoice", self.return_pos_invoice
        )

        vat_details = get_pos_vat_details(return_pos)

        current_net = abs(flt(return_pos.net_total, 2))
        current_vat = abs(flt(vat_details["amount"], 2))
        current_grand = abs(flt(return_pos.grand_total, 2))

        original_doc = frappe.get_doc(
            "POS Full Tax Invoice",
            self.original_full_tax_invoice,
        )

        previous_net = flt(original_doc.total_returned_net, 2)
        previous_vat = flt(original_doc.total_returned_vat, 2)
        previous_grand = flt(
            original_doc.total_returned_grand_total, 2
        )

        cumulative_net = flt(previous_net + current_net, 2)
        cumulative_vat = flt(previous_vat + current_vat, 2)
        cumulative_grand = flt(previous_grand + current_grand, 2)

        remaining_net = flt(
            original_doc.original_net_total - cumulative_net, 2
        )
        remaining_vat = flt(
            original_doc.original_vat_amount - cumulative_vat, 2
        )
        remaining_grand = flt(
            original_doc.original_grand_total - cumulative_grand, 2
        )

        if (
            remaining_net < -0.01
            or remaining_vat < -0.01
            or remaining_grand < -0.01
        ):
            frappe.throw(
                _(
                    "This Credit Note would exceed the remaining "
                    "amount of the Original Full Tax Invoice."
                )
            )

        # Lifetime sequence: never reuse a cancelled sequence.
        sequence = int(original_doc.credit_note_count or 0) + 1

        self.credit_note_sequence = sequence

        self.current_return_net = current_net
        self.current_return_vat = current_vat
        self.current_return_grand_total = current_grand

        self.cumulative_returned_net = cumulative_net
        self.cumulative_returned_vat = cumulative_vat
        self.cumulative_returned_grand_total = cumulative_grand

        self.remaining_net_after = max(remaining_net, 0)
        self.remaining_vat_after = max(remaining_vat, 0)
        self.remaining_grand_total_after = max(remaining_grand, 0)

        # Lock Branch Address before generating its document number.
        frappe.db.sql(
            """
            SELECT name
            FROM `tabBranch Address`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.branch_address,),
        )

        self.credit_note_number = make_autoname(
            self.get_credit_note_series()
        )
        self.credit_note_date = nowdate()
        self.issued_on = now_datetime()
        self.issued_by = frappe.session.user

    def on_submit(self):
        if self.document_type != "Full Tax Credit Note":
            return

        # Parent row remains serialized by before_submit_credit_note.
        active_count = frappe.db.count(
            "POS Full Tax Invoice",
            {
                "original_full_tax_invoice": self.original_full_tax_invoice,
                "document_type": "Full Tax Credit Note",
                "docstatus": 1,
            },
        )

        frappe.db.set_value(
            "POS Full Tax Invoice",
            self.original_full_tax_invoice,
            {
                "credit_note_count": max(
                    int(self.credit_note_sequence or 0),
                    int(
                        frappe.db.get_value(
                            "POS Full Tax Invoice",
                            self.original_full_tax_invoice,
                            "credit_note_count",
                        ) or 0
                    ),
                ),
                "active_credit_note_count": active_count,
                "total_returned_net": self.cumulative_returned_net,
                "total_returned_vat": self.cumulative_returned_vat,
                "total_returned_grand_total":
                    self.cumulative_returned_grand_total,
                "remaining_net": self.remaining_net_after,
                "remaining_vat": self.remaining_vat_after,
                "remaining_grand_total":
                    self.remaining_grand_total_after,
            },
            update_modified=False,
        )

    def before_cancel(self):
        if self.document_type != "Full Tax Credit Note":
            return

        frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Full Tax Invoice`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.original_full_tax_invoice,),
        )

        latest = frappe.db.sql(
            """
            SELECT name, credit_note_sequence
            FROM `tabPOS Full Tax Invoice`
            WHERE original_full_tax_invoice = %s
                AND document_type = 'Full Tax Credit Note'
                AND docstatus = 1
            ORDER BY credit_note_sequence DESC, creation DESC, name DESC
            LIMIT 1
            """,
            (self.original_full_tax_invoice,),
            as_dict=True,
        )

        if not latest or latest[0].name != self.name:
            latest_name = latest[0].name if latest else None
            frappe.throw(
                _(
                    "Credit Notes must be cancelled in LIFO order. "
                    "Cancel the latest submitted Credit Note first: {0}"
                ).format(latest_name or "-")
            )

    def on_cancel(self):
        if self.document_type != "Full Tax Credit Note":
            return

        frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Full Tax Invoice`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.original_full_tax_invoice,),
        )

        original_doc = frappe.get_doc(
            "POS Full Tax Invoice",
            self.original_full_tax_invoice,
        )

        latest = frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Full Tax Invoice`
            WHERE original_full_tax_invoice = %s
                AND document_type = 'Full Tax Credit Note'
                AND docstatus = 1
                AND name != %s
            ORDER BY credit_note_sequence DESC, creation DESC, name DESC
            LIMIT 1
            """,
            (self.original_full_tax_invoice, self.name),
            as_dict=True,
        )

        active_count = frappe.db.count(
            "POS Full Tax Invoice",
            {
                "original_full_tax_invoice": self.original_full_tax_invoice,
                "document_type": "Full Tax Credit Note",
                "docstatus": 1,
            },
        )

        if latest:
            previous_doc = frappe.get_doc(
                "POS Full Tax Invoice", latest[0].name
            )

            totals = {
                "total_returned_net":
                    previous_doc.cumulative_returned_net,
                "total_returned_vat":
                    previous_doc.cumulative_returned_vat,
                "total_returned_grand_total":
                    previous_doc.cumulative_returned_grand_total,
                "remaining_net": previous_doc.remaining_net_after,
                "remaining_vat": previous_doc.remaining_vat_after,
                "remaining_grand_total":
                    previous_doc.remaining_grand_total_after,
            }
        else:
            totals = {
                "total_returned_net": 0,
                "total_returned_vat": 0,
                "total_returned_grand_total": 0,
                "remaining_net": original_doc.original_net_total,
                "remaining_vat": original_doc.original_vat_amount,
                "remaining_grand_total":
                    original_doc.original_grand_total,
            }

        # Lifetime credit_note_count is intentionally never decremented.
        totals["active_credit_note_count"] = active_count

        frappe.db.set_value(
            "POS Full Tax Invoice",
            self.original_full_tax_invoice,
            totals,
            update_modified=False,
        )

    def before_submit(self):
        if self.document_type == "Full Tax Credit Note":
            self.before_submit_credit_note()
            return

        # Lock the source invoice to serialize submissions for the same POS Invoice.
        frappe.db.sql(
            """
            SELECT name
            FROM `tabPOS Invoice`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.pos_invoice,),
        )

        pos = self.get_original_pos_invoice()

        if pos.docstatus != 1 or pos.is_return:
            frappe.throw(
                _(
                    "Original POS Invoice is no longer eligible "
                    "for a Full Tax Invoice."
                )
            )

        if pos.pos_profile != self.pos_profile:
            frappe.throw(
                _("POS Profile does not match the original POS Invoice.")
            )

        if pos.branch != self.branch:
            frappe.throw(
                _("Branch does not match the original POS Invoice.")
            )

        # Lock Branch Address configuration while issuing its number.
        frappe.db.sql(
            """
            SELECT name
            FROM `tabBranch Address`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.branch_address,),
        )

        self.validate_original_pos_invoice()
        self.validate_buyer(
            previous=self.get_doc_before_save(),
            require_address=True,
        )
        self.validate_replacement()
        self.validate_duplicate_pos_invoice()

        if self.full_tax_invoice_number:
            frappe.throw(
                _("Full Tax Invoice Number must not be entered manually.")
            )

        series = self.get_branch_series()
        self.full_tax_invoice_number = make_autoname(series)
        self.issued_on = now_datetime()
        self.issued_by = frappe.session.user

def before_cancel_pos_invoice(doc, method=None):
    """Enforce Credit Note first, then LIFO for Return POS Invoices."""

    if not doc.is_return or not doc.return_against:
        return

    # Serialize cancellation checks for Returns of the same original POS.
    frappe.db.sql(
        """
        SELECT name
        FROM `tabPOS Invoice`
        WHERE name = %s
        FOR UPDATE
        """,
        (doc.return_against,),
    )

    frappe.db.sql(
        """
        SELECT name
        FROM `tabPOS Invoice`
        WHERE name = %s
        FOR UPDATE
        """,
        (doc.name,),
    )

    submitted_credit_notes = frappe.db.sql(
        """
        SELECT name
        FROM `tabPOS Full Tax Invoice`
        WHERE return_pos_invoice = %s
            AND document_type = 'Full Tax Credit Note'
            AND docstatus = 1
        LIMIT 1
        """,
        (doc.name,),
        as_dict=True,
    )

    if submitted_credit_notes:
        frappe.throw(
            _(
                "Cancel the submitted Credit Note {0} before "
                "cancelling this Return POS Invoice."
            ).format(submitted_credit_notes[0].name)
        )

    latest_return = frappe.db.sql(
        """
        SELECT name
        FROM `tabPOS Invoice`
        WHERE return_against = %s
            AND is_return = 1
            AND docstatus = 1
        ORDER BY creation DESC, name DESC
        LIMIT 1
        """,
        (doc.return_against,),
        as_dict=True,
    )

    if latest_return and latest_return[0].name != doc.name:
        frappe.throw(
            _(
                "Return POS Invoices must be cancelled in LIFO order. "
                "Cancel the latest Return POS Invoice first: {0}"
            ).format(latest_return[0].name)
        )


def _get_credit_note_action(return_pos_invoice):
    """Check whether a Return POS Invoice can create or open a Credit Note."""

    return_pos = frappe.get_doc("POS Invoice", return_pos_invoice)

    if (
        return_pos.docstatus != 1
        or not return_pos.is_return
        or not return_pos.return_against
    ):
        return {"show_button": False}

    original_full_tax_invoice = frappe.db.sql(
        """
        SELECT name
        FROM `tabPOS Full Tax Invoice`
        WHERE pos_invoice = %s
            AND docstatus = 1
            AND IFNULL(document_type, 'Full Tax Invoice') = 'Full Tax Invoice'
        ORDER BY modified DESC
        LIMIT 1
        """,
        (return_pos.return_against,),
        pluck=True,
    )

    if not original_full_tax_invoice:
        return {"show_button": False}

    submitted_credit_note = frappe.db.get_value(
        "POS Full Tax Invoice",
        {
            "return_pos_invoice": return_pos.name,
            "document_type": "Full Tax Credit Note",
            "docstatus": 1,
        },
        "name",
    )

    if submitted_credit_note:
        return {
            "show_button": False,
            "submitted_credit_note": submitted_credit_note,
        }

    draft_credit_note = frappe.db.get_value(
        "POS Full Tax Invoice",
        {
            "return_pos_invoice": return_pos.name,
            "document_type": "Full Tax Credit Note",
            "docstatus": 0,
        },
        "name",
    )

    return {
        "show_button": True,
        "draft_credit_note": draft_credit_note,
        "original_full_tax_invoice": original_full_tax_invoice[0],
    }


@frappe.whitelist()
def get_credit_note_action(return_pos_invoice):
    """Return button visibility and existing Draft information."""

    if not frappe.db.exists("POS Invoice", return_pos_invoice):
        frappe.throw(
            _("Return POS Invoice {0} does not exist.").format(return_pos_invoice)
        )

    return_pos = frappe.get_doc("POS Invoice", return_pos_invoice)

    if not frappe.has_permission("POS Invoice", "read", doc=return_pos):
        frappe.throw(_("You do not have permission to read this POS Invoice."))

    if not frappe.has_permission("POS Full Tax Invoice", "read"):
        frappe.throw(_("You do not have permission to read POS Full Tax Invoice documents."))

    return _get_credit_note_action(return_pos_invoice)


@frappe.whitelist()
def create_credit_note_from_return(return_pos_invoice):
    """Open an existing Draft or create a Credit Note Draft for a Return."""

    if not frappe.db.exists("POS Invoice", return_pos_invoice):
        frappe.throw(
            _("Return POS Invoice {0} does not exist.").format(return_pos_invoice)
        )

    return_pos = frappe.get_doc("POS Invoice", return_pos_invoice)

    if not frappe.has_permission("POS Invoice", "read", doc=return_pos):
        frappe.throw(_("You do not have permission to read this POS Invoice."))

    if not frappe.has_permission("POS Full Tax Invoice", "read"):
        frappe.throw(_("You do not have permission to read POS Full Tax Invoice documents."))

    # Lock the Return POS Invoice to prevent concurrent Draft creation.
    frappe.db.sql(
        """
        SELECT name
        FROM `tabPOS Invoice`
        WHERE name = %s
        FOR UPDATE
        """,
        (return_pos_invoice,),
    )

    action = _get_credit_note_action(return_pos_invoice)

    if action.get("submitted_credit_note"):
        frappe.throw(
            _("This Return POS Invoice already has a submitted Credit Note: {0}").format(
                action["submitted_credit_note"]
            )
        )

    if not action.get("show_button"):
        frappe.throw(
            _("A submitted Full Tax Invoice for the original POS Invoice is required first.")
        )

    # If a Draft already exists, open it instead of creating another one.
    if action.get("draft_credit_note"):
        return {
            "name": action["draft_credit_note"],
            "created": False,
        }

    if not frappe.has_permission("POS Full Tax Invoice", "create"):
        frappe.throw(_("You do not have permission to create a Credit Note."))

    doc = frappe.new_doc("POS Full Tax Invoice")
    doc.document_type = "Full Tax Credit Note"
    doc.pos_invoice = return_pos.return_against
    doc.return_pos_invoice = return_pos.name
    doc.original_full_tax_invoice = action["original_full_tax_invoice"]

    doc.insert()

    return {
        "name": doc.name,
        "created": True,
    }
