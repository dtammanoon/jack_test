import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime


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


class POSFullTaxInvoice(Document):

    def validate(self):
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
        self.original_vat_amount = pos.total_taxes_and_charges or 0
        self.original_grand_total = pos.grand_total or 0
        self.original_paid_amount = pos.paid_amount or 0

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

    def before_submit(self):
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
