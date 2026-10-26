(() => {
    const DOCTYPES = {
        'Request for Quotation': null,
        'Supplier Quotation':    'supplier',
        'Purchase Order':        'supplier',
        'Purchase Receipt':      'supplier',
        'Purchase Invoice':      'supplier'
    };

    // ฟิลด์ใน Branch Address : [ฟิลด์ที่อยู่, ฟิลด์ display] ในเอกสารซื้อ
    const FIELD_MAP = {
        billing_address:  ['billing_address',  'billing_address_display'],
        shipping_address: ['shipping_address', 'shipping_address_display'],
    };

    // ช่วงเวลาที่จะใส่ค่าซ้ำ เผื่อ ERPNext ใส่ที่อยู่หลักทับทีหลัง (มิลลิวินาที)
    const RETRY_DELAYS = [800, 2000];

    function session_branch() {
        return frappe.defaults.get_user_default('branch')
            || frappe.defaults.get_user_default('Branch');
    }

    function get_branch(frm) {
        return frm.fields_dict.branch ? frm.doc.branch : session_branch();
    }

    function is_fresh_new(frm) {
        return frm.is_new()
            && !frm.doc.amended_from
            && !(frm.doc.items || []).some(row => row.item_code);
    }

    async function set_address(frm, addr_field, display_field, addr) {
        if (frm.doc[addr_field] !== addr) {
            await frm.set_value(addr_field, addr);
        }
        if (!display_field || !frm.fields_dict[display_field]) return;

        // ใส่ display เอง ไม่ต้องพึ่ง trigger ของ ERPNext
        const r = await frappe.call({
            method: 'frappe.contacts.doctype.address.address.get_address_display',
            args: { address_dict: addr },
        });
        if (r.message && frm.is_new() && frm.doc[addr_field] === addr) {
            frm.set_value(display_field, r.message);
        }
    }

    async function apply_branch_address(frm) {
        if (!frm._branch_pur_fresh || !frm.is_new()) return;

        const branch = get_branch(frm);
        if (!branch) return;

        const targets = Object.entries(FIELD_MAP)
            .filter(([, [addr_field]]) => frm.fields_dict[addr_field]);
        if (!targets.length) return;

        const r = await frappe.db.get_value('Branch Address', { branch }, targets.map(([src]) => src));
        const v = r.message || {};
        if (!frm.is_new()) return;

        for (const [src, [addr_field, display_field]] of targets) {
            if (v[src]) {
                await set_address(frm, addr_field, display_field, v[src]);
            }
        }
    }

    Object.entries(DOCTYPES).forEach(([dt, party_field]) => {
        const handlers = {
            onload(frm) {
                frm._branch_pur_fresh = is_fresh_new(frm);
                if (!frm._branch_pur_fresh) return;

                if (frm.fields_dict.branch && !frm.doc.branch) {
                    const b = session_branch();
                    if (b) frm.doc.branch = b;
                }
            },

            refresh(frm) {
                if (frm._branch_pur_fresh && frm.is_new() && !frm._branch_pur_done) {
                    frm._branch_pur_done = true;
                    if (frm.fields_dict.branch) frm.refresh_field('branch');

                    frappe.after_ajax(() => apply_branch_address(frm));
                    RETRY_DELAYS.forEach(ms => setTimeout(() => apply_branch_address(frm), ms));
                }
            },

            company(frm) {
                frappe.after_ajax(() => apply_branch_address(frm));
            },
        };

        if (party_field) {
            handlers[party_field] = frm => frappe.after_ajax(() => apply_branch_address(frm));
        }

        frappe.ui.form.on(dt, handlers);
    });
})();