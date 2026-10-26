(() => {
    const RETRY_DELAYS = [500, 1000, 2000, 3000];

    function session_branch() {
        return frappe.defaults.get_user_default('branch')
            || frappe.defaults.get_user_default('Branch');
    }

    async function apply_address(frm) {
        if (!frm.is_new() || frm.doc.amended_from) return;

        // กรณีที่ 1: มีการดึงมาจาก Supplier Quotation
        const sq_name = frm.doc.supplier_quotation;
        if (sq_name) {
            try {
                const r = await frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'Supplier Quotation',
                        name: sq_name
                    }
                });

                const doc = r && r.message;
                if (!doc || !frm.is_new()) return;

                if (doc.billing_address && frm.doc.company_address !== doc.billing_address) {
                    await frm.set_value('company_address', doc.billing_address);
                }

                if (doc.billing_address_display && frm.doc.company_address_display !== doc.billing_address_display) {
                    await frm.set_value('company_address_display', doc.billing_address_display);
                }
                return;
            } catch (e) {
                console.error("Could not fetch Supplier Quotation address:", e);
            }
        }

        // กรณีที่ 2: ไม่มี Supplier Quotation ให้ดึงจาก Branch ใน Session Defaults
        if (frm.fields_dict.branch && !frm.doc.branch) {
            const b = session_branch();
            if (b) {
                await frm.set_value('branch', b);
            }
        }

        const branch = frm.fields_dict.branch ? frm.doc.branch : session_branch();
        if (!branch || !frm.fields_dict.company_address) return;

        try {
            // ดึงเฉพาะ billing_address ป้องกัน Error field not permitted
            const r = await frappe.db.get_value('Branch Address', { branch }, ['billing_address']);
            const v = r && r.message;
            if (!v || !frm.is_new()) return;

            if (v.billing_address && frm.doc.company_address !== v.billing_address) {
                await frm.set_value('company_address', v.billing_address);
            }
        } catch (e) {
            console.error("Could not fetch Branch Address:", e);
        }
    }

    frappe.ui.form.on('Quotation', {
        refresh(frm) {
            if (!frm.is_new()) return;
            RETRY_DELAYS.forEach(ms => {
                setTimeout(() => {
                    apply_address(frm);
                }, ms);
            });
        },

        supplier_quotation(frm) {
            if (frm.is_new()) {
                frappe.after_ajax(() => apply_address(frm));
            }
        },

        branch(frm) {
            if (frm.is_new() && !frm.doc.supplier_quotation) {
                frappe.after_ajax(() => apply_address(frm));
            }
        }
    });
})();