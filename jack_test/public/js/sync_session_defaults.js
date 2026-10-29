(() => {
    // key ของ session default -> fieldname ในฟอร์ม
    const FIELD_MAP = {
        company: "company",
        branch: "branch",
        cost_center: "cost_center",
    };

    // DocType ที่ไม่ต้องการให้ sync
    const SKIP_DOCTYPES = new Set([
        "Session Default Settings", "User", "Company", "Branch", "Cost Center",
    ]);

    // DocType ที่อยากให้ sync ทันทีตอนแก้ฟิลด์ (ก่อน Save)
    const LIVE_DOCTYPES = [
        "Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order",
        "Delivery Note", "Purchase Receipt", "Quotation", "Material Request",
        "Payment Entry", "Stock Entry", "Expense Claim",
    ];

    const METHOD =
        "frappe.core.doctype.session_default_settings.session_default_settings.set_session_default_values";

    let pending = null;

    function collect(frm) {
        const values = {};
        for (const [key, field] of Object.entries(FIELD_MAP)) {
            if (!frm.fields_dict[field]) continue;          // ฟอร์มนี้ไม่มีฟิลด์นี้
            const val = frm.doc[field];
            if (!val) continue;
            const current = (frappe.boot.user.defaults || {})[key];
            if (current !== val) values[key] = val;
        }
        return values;
    }

    function sync(frm) {
        if (!frm || !frm.doc || SKIP_DOCTYPES.has(frm.doctype)) return;

        const values = collect(frm);
        if (!Object.keys(values).length) return;

        const sig = JSON.stringify(values);
        if (pending === sig) return;                        // กันยิงซ้ำ
        pending = sig;

        frappe.call({
            method: METHOD,
            args: {
                default_values: values,
                jack_silent_sync: 1,      // marker: ต้องอยู่ใน args เท่านั้น
            },
            freeze: false,
        }).then((r) => {
            if (r.message === "success") {
                for (const [k, v] of Object.entries(values)) {
                    frappe.defaults.set_user_default_local(k, v);
                }
                frappe.show_alert({
                    message: __("Session Defaults updated: {0}",
                        [Object.values(values).join(", ")]),
                    indicator: "blue",
                }, 3);
            }
        }).always(() => { pending = null; });
    }

    // 1) ตอนเปิดหรือ refresh ฟอร์ม (ทุก DocType)
    $(document).on("form-refresh", (e, frm) => sync(frm));

    // 2) ตอนผู้ใช้เปลี่ยนค่าฟิลด์ (เฉพาะ DocType ที่ระบุ)
    const handlers = {};
    Object.values(FIELD_MAP).forEach((f) => (handlers[f] = (frm) => sync(frm)));
    LIVE_DOCTYPES.forEach((dt) => frappe.ui.form.on(dt, handlers));
})();