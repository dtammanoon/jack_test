(() => {
    // Quotation แยกไปอยู่ไฟล์ quotation_from_supplier.js แล้ว
    const BRANCH_ADDR_DOCTYPES = {
        'Sales Order':   'customer',
        'Delivery Note': 'customer',
        'Sales Invoice': 'customer',
    };

    // ฟิลด์ใน Branch Address : [ฟิลด์ที่อยู่, ฟิลด์ display] ในเอกสารขาย
    const FIELD_MAP = {
        billing_address: ['company_address', 'company_address_display'],
    };

    const RETRY_DELAYS = [800, 2000, 3500];

    function session_branch() {
        return frappe.defaults.get_user_default('branch')
            || frappe.defaults.get_user_default('Branch');
    }

    // เอกสารใหม่ที่ยังไม่ Save (รวมที่ map มาจาก SO/DN) และไม่ใช่ Amend
    function is_valid_new(frm) {
        return frm.is_new() && !frm.doc.amended_from;
    }

    async function set_address(frm, addr_field, display_field, addr) {
        if (frm.doc[addr_field] !== addr) {
            await frm.set_value(addr_field, addr);
        }
        if (!display_field || !frm.fields_dict[display_field]) return;

        const r = await frappe.call({
            method: 'frappe.contacts.doctype.address.address.get_address_display',
            args: { address_dict: addr },
        });
        if (r.message && frm.is_new() && frm.doc[addr_field] === addr) {
            await frm.set_value(display_field, r.message);
        }
    }

    async function apply_branch_address(frm) {
        if (!is_valid_new(frm)) return;

        if (frm.fields_dict.branch && !frm.doc.branch) {
            const b = session_branch();
            if (b) await frm.set_value('branch', b);
        }

        const branch = frm.fields_dict.branch ? frm.doc.branch : session_branch();
        if (!branch) return;

        const targets = Object.entries(FIELD_MAP)
            .filter(([, [addr_field]]) => frm.fields_dict[addr_field]);
        if (!targets.length) return;

        // ดึงเฉพาะชื่อที่อยู่ (get_value ไม่อนุญาตฟิลด์ *_display)
        const r = await frappe.db.get_value('Branch Address', { branch }, targets.map(([src]) => src));
        const v = r.message || {};
        if (!frm.is_new()) return;

        for (const [src, [addr_field, display_field]] of targets) {
            if (v[src]) {
                await set_address(frm, addr_field, display_field, v[src]);
            }
        }
    }

    Object.entries(BRANCH_ADDR_DOCTYPES).forEach(([dt, party_field]) => {
        frappe.ui.form.on(dt, {
            refresh(frm) {
                if (is_valid_new(frm) && !frm._branch_addr_done) {
                    frm._branch_addr_done = true;
                    frappe.after_ajax(() => apply_branch_address(frm));
                    RETRY_DELAYS.forEach(ms => setTimeout(() => apply_branch_address(frm), ms));
                }
            },

            [party_field](frm) {
                frappe.after_ajax(() => apply_branch_address(frm));
            },

            company(frm) {
                frappe.after_ajax(() => apply_branch_address(frm));
            },

            branch(frm) {
                frappe.after_ajax(() => apply_branch_address(frm));
            },
        });
    });
})();