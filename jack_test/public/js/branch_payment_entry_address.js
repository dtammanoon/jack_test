(() => {
    // ชื่อฟิลด์ใน Branch Address ที่เป็นที่อยู่ Bill To ไล่ลองตามลำดับ
    const SOURCE_FIELDS = ['billto_address', 'bill_to_address', 'billing_address'];

    const TARGET_FIELD = 'company_tax_address';
    const TARGET_DISPLAY = 'company_tax_address_display';

    const RETRY_DELAYS = [800, 2000, 3500];

    function session_branch() {
        return frappe.defaults.get_user_default('branch')
            || frappe.defaults.get_user_default('Branch');
    }

    function is_valid_new(frm) {
        return frm.is_new() && !frm.doc.amended_from;
    }

    async function get_branch_address_doc(branch) {
        try {
            const r = await frappe.call({
                method: 'frappe.client.get',
                args: { doctype: 'Branch Address', filters: { branch } },
                silent: true,
            });
            return r.message || null;
        } catch (e) {
            console.error('Could not fetch Branch Address for branch:', branch, e);
            return null;
        }
    }

    async function apply_branch_address(frm, docname) {
        // ยกเลิกถ้าผู้ใช้เปลี่ยนไปเปิดเอกสารใบอื่นแล้ว
        if (frm.doc.name !== docname) return;
        if (!is_valid_new(frm) || !frm.fields_dict[TARGET_FIELD]) return;

        if (frm.fields_dict.branch && !frm.doc.branch) {
            const b = session_branch();
            if (b) await frm.set_value('branch', b);
        }

        const branch = frm.fields_dict.branch ? frm.doc.branch : session_branch();
        if (!branch) return;

        const ba = await get_branch_address_doc(branch);
        if (!ba || frm.doc.name !== docname || !frm.is_new()) return;

        const src = SOURCE_FIELDS.find(f => ba[f]);
        if (!src) {
            const available = Object.keys(ba).filter(k => k.includes('address'));
            console.warn('Branch Address: ไม่พบฟิลด์ใน SOURCE_FIELDS ฟิลด์ที่อยู่ที่มีจริง:', available);
            return;
        }

        const addr = ba[src];
        if (frm.doc[TARGET_FIELD] !== addr) {
            await frm.set_value(TARGET_FIELD, addr);
        }

        if (!frm.fields_dict[TARGET_DISPLAY]) return;
        const r = await frappe.call({
            method: 'frappe.contacts.doctype.address.address.get_address_display',
            args: { address_dict: addr },
        });
        if (r.message && frm.doc.name === docname && frm.is_new() && frm.doc[TARGET_FIELD] === addr) {
            await frm.set_value(TARGET_DISPLAY, r.message);
        }
    }

    function schedule(frm) {
        const docname = frm.doc.name;
        frappe.after_ajax(() => apply_branch_address(frm, docname));
    }

    frappe.ui.form.on('Payment Entry', {
        refresh(frm) {
            if (!is_valid_new(frm)) return;

            // ผูกกับชื่อเอกสาร ไม่ใช่ตัว frm เพราะ frm ถูกใช้ซ้ำทุกใบ
            if (frm._branch_pay_done === frm.doc.name) return;
            frm._branch_pay_done = frm.doc.name;

            const docname = frm.doc.name;
            frappe.after_ajax(() => apply_branch_address(frm, docname));
            RETRY_DELAYS.forEach(ms =>
                setTimeout(() => apply_branch_address(frm, docname), ms));
        },
        company(frm)    { schedule(frm); },
        branch(frm)     { schedule(frm); },
        party_type(frm) { schedule(frm); },
        party(frm)      { schedule(frm); },
    });
})();