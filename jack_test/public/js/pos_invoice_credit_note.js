frappe.ui.form.on("POS Invoice", {
    refresh(frm) {
        // แสดงปุ่มเฉพาะ Return POS Invoice ที่ Submit แล้ว
        if (
            frm.doc.docstatus !== 1 ||
            !frm.doc.is_return ||
            !frm.doc.return_against
        ) {
            return;
        }

        const method =
            "jack_test.jack_test.doctype.pos_full_tax_invoice.pos_full_tax_invoice";

        // ให้ Server ตรวจสอบสิทธิ์และเงื่อนไขก่อนแสดงปุ่ม
        frappe.call({
            method: `${method}.get_credit_note_action`,
            args: {
                return_pos_invoice: frm.doc.name
            },
            callback(r) {
                if (!r.message || !r.message.show_button) {
                    return;
                }

                const label = __("Create / Open POS Full Tax Credit Note");

                // ป้องกันปุ่มซ้ำเมื่อ refresh ฟอร์ม
                frm.remove_custom_button(label, __("Create"));

                frm.add_custom_button(label, () => {
                    frappe.call({
                        method: `${method}.create_credit_note_from_return`,
                        args: {
                            return_pos_invoice: frm.doc.name
                        },
                        freeze: true,
                        freeze_message: __("Preparing Credit Note..."),
                        callback(result) {
                            if (result.message && result.message.name) {
                                frappe.set_route(
                                    "Form",
                                    "POS Full Tax Invoice",
                                    result.message.name
                                );
                            }
                        }
                    });
                }, __("Create"));
            }
        });
    }
});
