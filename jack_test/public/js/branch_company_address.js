const BRANCH_ADDR_DOCTYPES = {
    'Sales Order':   'customer',
    'Delivery Note': 'customer',
    'Sales Invoice': 'customer'
};

//    'Quotation':     'party_name',

// เอกสารใหม่จริงๆ = ยังไม่ Save, ไม่ใช่ Amend และยังไม่มีรายการสินค้า
// (เอกสารที่สร้างต่อจากใบก่อนหน้าหรือ Duplicate จะมีรายการสินค้าติดมาตั้งแต่เปิดฟอร์ม)
function is_fresh_new(frm) {
    return frm.is_new()
        && !frm.doc.amended_from
        && !(frm.doc.items || []).some(row => row.item_code);
}

function set_branch_company_address(frm) {
    if (!frm._branch_addr_fresh || !frm.is_new() || !frm.doc.branch) return;

    frappe.db.get_value('Branch Address', { branch: frm.doc.branch }, 'billing_address')
        .then(r => {
            const addr = r.message && r.message.billing_address;
            if (addr && frm.is_new() && frm.doc.company_address !== addr) {
                frm.set_value('company_address', addr);
            }
        });
}

Object.entries(BRANCH_ADDR_DOCTYPES).forEach(([dt, party_field]) => {
    frappe.ui.form.on(dt, {
        setup(frm) {
            frm.set_query('company_address', () => ({ filters: {} }));
        },

        onload(frm) {
            // เช็คครั้งเดียวตอนเปิดฟอร์ม แล้วจำไว้
            frm._branch_addr_fresh = is_fresh_new(frm);
            if (!frm._branch_addr_fresh) return;

            if (!frm.doc.branch) {
                const b = frappe.defaults.get_user_default('branch')
                       || frappe.defaults.get_user_default('Branch');
                if (b) frm.doc.branch = b;   // ใส่ค่าตรงๆ ไม่ trigger event
            }
        },

        refresh(frm) {
            if (frm._branch_addr_fresh && frm.is_new() && !frm._branch_addr_done) {
                frm._branch_addr_done = true;
                frm.refresh_field('branch');
                frappe.after_ajax(() => set_branch_company_address(frm));
            }
        },

        // ERPNext จะเขียน company_address ทับเมื่อเลือกลูกค้าหรือบริษัท
        // ถ้าไม่ใส่กลับ ที่อยู่สาขาจะหายทันทีที่ผู้ใช้เลือกลูกค้า
        [party_field](frm) {
            frappe.after_ajax(() => set_branch_company_address(frm));
        },

        company(frm) {
            frappe.after_ajax(() => set_branch_company_address(frm));
        },
    });
});