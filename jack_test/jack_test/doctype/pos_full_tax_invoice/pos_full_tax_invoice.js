
frappe.ui.form.on("POS Full Tax Invoice", {
    setup(frm) {
        frm.set_query("pos_invoice", () => {
            return {
                filters: {
                    docstatus: 1,
                    is_return: 0
                }
            };
        });

        frm.set_query("replacement_of", () => {
            return {
                filters: {
                    docstatus: 2,
                    pos_invoice: frm.doc.pos_invoice
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

        frappe.db.get_value(
            "POS Invoice",
            frm.doc.pos_invoice,
            [
                "docstatus",
                "is_return",
                "company",
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
        ).then(r => {
            const d = r.message;

            if (!d) {
                return;
            }

            if (d.docstatus !== 1 || d.is_return) {
                frappe.msgprint(
                    __("Select a submitted, non-return POS Invoice.")
                );

                frm.set_value("pos_invoice", "");
                return;
            }

            const values = {
                company: d.company,
                pos_profile: d.pos_profile,
                pos_invoice_number: frm.doc.pos_invoice,
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

            Object.keys(values).forEach(field => {
                frm.set_value(field, values[field]);
            });

            if (!frm.doc.buyer_name) {
                frm.set_value(
                    "buyer_name",
                    d.customer_name || d.customer
                );
            }

            if (!frm.doc.buyer_tax_id) {
                frm.set_value("buyer_tax_id", d.tax_id);
            }

            if (!frm.doc.buyer_address) {
                frm.set_value("buyer_address", d.address_display);
            }
        });
    }
});
