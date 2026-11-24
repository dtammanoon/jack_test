(() => {
    // key ของ session default -> fieldname ในฟอร์ม
    const FIELD_MAP = {
        company: "company",
        branch: "branch",
        cost_center: "cost_center",
    };

    const SKIP_DOCTYPES = new Set([
        "Session Default Settings", "Session Default Selected",
        "User", "Company", "Branch", "Cost Center",
    ]);

    // DocType ที่ให้ sync ทันทีตอนแก้ฟิลด์ (ก่อน Save)
    const LIVE_DOCTYPES = [
        "Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order",
        "Delivery Note", "Purchase Receipt", "Quotation", "Material Request",
        "Payment Entry", "Stock Entry", "Expense Claim",
    ];

    const SET_METHOD =
        "frappe.core.doctype.session_default_settings.session_default_settings.set_session_default_values";
    const GET_SELECTED_METHOD = "jack_test.api.session_defaults.get_selected";

    let selected = {};          // ค่าที่ผู้ใช้เลือกเอง (จาก Session Default Selected)
    let selectedPromise = null;
    let busy = false;
    let again = false;
    let timer = null;

    function loadSelected() {
        if (!selectedPromise) {
            selectedPromise = frappe.xcall(GET_SELECTED_METHOD)
                .then((r) => (selected = r || {}))
                .catch(() => (selected = {}));
        }
        return selectedPromise;
    }

    // ฟอร์มเอกสารที่กำลังเปิดอยู่จริง (ถ้าไม่ได้อยู่ในฟอร์ม จะคืน null)
    function currentForm() {
        const route = frappe.get_route() || [];
        if (route[0] !== "Form") return null;

        const frm = window.cur_frm;
        if (!frm || !frm.doc || frm.doctype !== route[1]) return null;
        if (SKIP_DOCTYPES.has(frm.doctype)) return null;
        return frm;
    }

    // ค่าที่ Session Defaults "ควรจะเป็น" ณ ตอนนี้
    function targetValues() {
        const target = Object.assign({}, selected);   // ฐาน = ค่าที่เลือกเก็บไว้

        const frm = currentForm();
        if (frm) {
            for (const [key, field] of Object.entries(FIELD_MAP)) {
                if (frm.fields_dict[field] && frm.doc[field]) {
                    target[key] = frm.doc[field];      // ทับด้วยค่าจากเอกสาร
                }
            }
        }
        return target;
    }

    function diffWithCurrent(target) {
        const current = frappe.boot.user.defaults || {};
        const out = {};
        for (const [k, v] of Object.entries(target)) {
            if (v && current[k] !== v) out[k] = v;
        }
        return out;
    }

    async function reconcile() {
        if (busy) { again = true; return; }
        busy = true;

        try {
            await loadSelected();
            const values = diffWithCurrent(targetValues());
            if (!Object.keys(values).length) return;

            const r = await frappe.xcall(SET_METHOD, {
                default_values: values,
                jack_silent_sync: 1,   // ไม่บันทึกเป็นค่าที่เลือก และไม่ redirect ไป Desktop
            });

            if (r === "success") {
                for (const [k, v] of Object.entries(values)) {
                    frappe.defaults.set_user_default_local(k, v);
                }
                frappe.show_alert({
                    message: __("Session Defaults: {0}", [Object.values(values).join(", ")]),
                    indicator: currentForm() ? "blue" : "green",
                }, 3);
            }
        } catch (e) {
            console.error("[jack_test] session defaults sync failed", e);
        } finally {
            busy = false;
            if (again) { again = false; schedule(); }
        }
    }

    function schedule() {
        clearTimeout(timer);
        timer = setTimeout(reconcile, 300);
    }

    // เปิดหรือ refresh ฟอร์ม
    $(document).on("form-refresh", schedule);

    // เปลี่ยนหน้า (รวมถึงออกจากเอกสาร) -> คืนค่าที่เลือกไว้
    if (frappe.router && frappe.router.on) {
        frappe.router.on("change", schedule);
    }

    // แก้ค่า Company / Branch / Cost Center ในฟอร์ม
    const handlers = {};
    Object.values(FIELD_MAP).forEach((f) => (handlers[f] = schedule));
    LIVE_DOCTYPES.forEach((dt) => frappe.ui.form.on(dt, handlers));
})();