
async function load_buyer_snapshot(frm) {
    const customer_name = frm.doc.buyer_customer;
    const address_name = frm.doc.buyer_customer_address;

    if (!customer_name || !address_name) {
        return;
    }

    const [customer_result, address_result] = await Promise.all([
        frappe.db.get_value(
            "Customer",
            customer_name,
            ["customer_name", "tax_id", "branch_code", "email_id"]
        ),
        frappe.db.get_value(
            "Address",
            address_name,
            [
                "address_title",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "pincode",
                "country",
                "tax_id",
                "branch_code",
                "email_id"
            ]
        )
    ]);

    // Ignore stale responses if the user changed the selection.
    if (
        frm.doc.buyer_customer !== customer_name ||
        frm.doc.buyer_customer_address !== address_name
    ) {
        return;
    }

    const customer = customer_result.message || {};
    const address = address_result.message || {};

    const address_parts = [
        address.address_line1,
        address.address_line2,
        address.city,
        address.state,
        address.pincode,
        address.country
    ].filter(Boolean);

    await frm.set_value({
        buyer_name: customer.customer_name || customer_name,
        buyer_tax_id: address.tax_id || customer.tax_id || "",
        buyer_branch: address.branch_code || customer.branch_code || "",
        buyer_address: address_parts.join(" "),
        buyer_email: address.email_id || customer.email_id || ""
    });
}


async function select_default_buyer_address(frm) {
    const customer = frm.doc.buyer_customer;

    if (!customer) {
        return;
    }

    const request_id = (frm.__buyer_address_request || 0) + 1;
    frm.__buyer_address_request = request_id;

    await frm.set_value({
        buyer_customer_address: "",
        buyer_name: "",
        buyer_tax_id: "",
        buyer_branch: "",
        buyer_address: "",
        buyer_email: ""
    });

    const result = await frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Address",
            filters: [
                ["Dynamic Link", "link_doctype", "=", "Customer"],
                ["Dynamic Link", "link_name", "=", customer],
                ["Address", "disabled", "=", 0]
            ],
            fields: [
                "name",
                "is_primary_address",
                "creation"
            ],
            order_by: "is_primary_address desc, creation desc",
            limit_page_length: 100
        }
    });

    if (
        frm.__buyer_address_request !== request_id ||
        frm.doc.buyer_customer !== customer
    ) {
        return;
    }

    const addresses = result.message || [];

    if (addresses.length) {
        // Primary first; if none, newest creation first.
        await frm.set_value(
            "buyer_customer_address",
            addresses[0].name
        );
    } else {
        // No linked Address: keep the Customer, but notify the user.
        const customer_result = await frappe.db.get_value(
            "Customer",
            customer,
            ["customer_name", "tax_id", "branch_code", "email_id"]
        );

        if (
            frm.__buyer_address_request !== request_id ||
            frm.doc.buyer_customer !== customer
        ) {
            return;
        }

        const d = customer_result.message || {};

        await frm.set_value({
            buyer_name: d.customer_name || customer,
            buyer_tax_id: d.tax_id || "",
            buyer_branch: d.branch_code || "",
            buyer_email: d.email_id || ""
        });

        frappe.msgprint(
            __("This Buyer Customer has no linked Address. Please create or link an Address before issuing the Full Tax Invoice.")
        );
    }
}


frappe.ui.form.on("POS Full Tax Invoice", {
    setup(frm) {
        // Search Buyer Customer by Customer ID, Name and Tax ID.
        frm.set_query("buyer_customer", () => ({
            query: "jack_test.jack_test.doctype.pos_full_tax_invoice.pos_full_tax_invoice.buyer_customer_query"
        }));

        frm.set_query("pos_invoice", () => ({
            filters: {
                docstatus: 1,
                is_return: 0
            }
        }));

        frm.set_query("replacement_of", () => ({
            filters: {
                docstatus: 2,
                pos_invoice: frm.doc.pos_invoice
            }
        }));

        // Buyer Address is restricted to the selected Buyer Customer.
        frm.set_query("buyer_customer_address", () => {
            if (!frm.doc.buyer_customer) {
                return {
                    filters: {
                        name: "__no_customer_selected__"
                    }
                };
            }

            return {
                query: "frappe.contacts.doctype.address.address.address_query",
                filters: {
                    link_doctype: "Customer",
                    link_name: frm.doc.buyer_customer,
                    disabled: 0
                }
            };
        });
    },

    refresh(frm) {
        if (frm.doc.pos_invoice) {
            frm.add_custom_button(
                __("Open Original POS Invoice"),
                () => {
                    frappe.set_route(
                        "Form",
                        "POS Invoice",
                        frm.doc.pos_invoice
                    );
                }
            );
        }

        if (frm.doc.replacement_of) {
            frm.add_custom_button(
                __("Open Cancelled Full Tax Invoice"),
                () => {
                    frappe.set_route(
                        "Form",
                        "POS Full Tax Invoice",
                        frm.doc.replacement_of
                    );
                }
            );
        }
    },

    pos_invoice(frm) {
        if (!frm.doc.pos_invoice) {
            return;
        }

        const selected_invoice = frm.doc.pos_invoice;

        frappe.db.get_value(
            "POS Invoice",
            selected_invoice,
            [
                "docstatus",
                "is_return",
                "company",
                "branch",
                "pos_profile",
                "posting_date",
                "posting_time",
                "customer",
                "customer_name",
                "tax_id",
                "customer_address",
                "address_display",
                "consolidated_invoice",
                "net_total",
                "total_taxes_and_charges",
                "grand_total",
                "paid_amount"
            ]
        ).then(async r => {
            const d = r.message;

            if (!d || frm.doc.pos_invoice !== selected_invoice) {
                return;
            }

            if (d.docstatus !== 1 || d.is_return) {
                frappe.msgprint(
                    __("Select a submitted, non-return POS Invoice.")
                );

                await frm.set_value("pos_invoice", "");
                return;
            }

            // Reset buyer selection when the original POS Invoice changes.
            await frm.set_value({
                buyer_customer: "",
                buyer_customer_address: "",
                buyer_name: "",
                buyer_tax_id: "",
                buyer_branch: "",
                buyer_address: "",
                buyer_email: ""
            });

            const values = {
                company: d.company,
                branch: d.branch,
                branch_address: d.branch,
                pos_profile: d.pos_profile,
                pos_invoice_number: selected_invoice,
                pos_posting_date: d.posting_date,
                pos_posting_time: d.posting_time,
                full_tax_invoice_date: d.posting_date,
                customer: d.customer,
                original_customer_name: d.customer_name,
                original_tax_id: d.tax_id,
                pos_customer_address: d.customer_address,
                pos_consolidated_invoice: d.consolidated_invoice,
                original_net_total: d.net_total,
                original_vat_amount: d.total_taxes_and_charges,
                original_grand_total: d.grand_total,
                original_paid_amount: d.paid_amount
            };

            await frm.set_value(values);

            // Default Buyer Customer to the original POS Customer.
            if (d.customer) {
                await frm.set_value("buyer_customer", d.customer);
            }
        });
    },

    buyer_customer(frm) {
        if (!frm.doc.buyer_customer) {
            frm.__buyer_address_request =
                (frm.__buyer_address_request || 0) + 1;

            frm.set_value({
                buyer_customer_address: "",
                buyer_name: "",
                buyer_tax_id: "",
                buyer_branch: "",
                buyer_address: "",
                buyer_email: ""
            });

            return;
        }

        select_default_buyer_address(frm);
    },

    buyer_customer_address(frm) {
        if (frm.doc.buyer_customer && frm.doc.buyer_customer_address) {
            load_buyer_snapshot(frm);
        }
    }
});
