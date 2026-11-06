(() => {
    // DocType -> [[ตารางลูก, Child DocType, ฟิลด์คลัง, ฟิลด์ชั้นวาง]]
    // ถ้าเป็นหัวเอกสาร ให้ใส่ตารางลูกและ Child DocType เป็น null
    const SHELF_FIELD_MAP = {
        "Stock Entry": [
            ["items", "Stock Entry Detail", "s_warehouse", "shelf"],
            ["items", "Stock Entry Detail", "t_warehouse", "to_shelf"],
        ],
        "Purchase Receipt": [
            ["items", "Purchase Receipt Item", "warehouse", "shelf"],
            ["items", "Purchase Receipt Item", "from_warehouse", "from_shelf"],
        ],
        "Purchase Invoice": [
            ["items", "Purchase Invoice Item", "warehouse", "shelf"],
            ["items", "Purchase Invoice Item", "from_warehouse", "from_shelf"],
        ],
        "Delivery Note": [
            ["items", "Delivery Note Item", "warehouse", "shelf"],
            ["items", "Delivery Note Item", "target_warehouse", "to_shelf"],
            ["packed_items", "Packed Item", "warehouse", "shelf"],
        ],
        "Sales Invoice": [
            ["items", "Sales Invoice Item", "warehouse", "shelf"],
            ["items", "Sales Invoice Item", "target_warehouse", "to_shelf"],
            ["packed_items", "Packed Item", "warehouse", "shelf"],
        ],
        "POS Invoice": [
            ["items", "POS Invoice Item", "warehouse", "shelf"],
            ["packed_items", "Packed Item", "warehouse", "shelf"],
        ],
        "Stock Reconciliation": [
            ["items", "Stock Reconciliation Item", "warehouse", "shelf"],
        ],
        "Pick List": [
            ["locations", "Pick List Item", "warehouse", "shelf"],
        ],
        "Subcontracting Receipt": [
            ["items", "Subcontracting Receipt Item", "warehouse", "shelf"],
        ],
        "Putaway Rule": [
            [null, null, "warehouse", "shelf"],
        ],
    };

    // ให้ช่องชั้นวางแสดงเฉพาะชั้นของคลังที่เลือกในแถวนั้น
    function shelf_query(wh_field) {
        return (doc, cdt, cdn) => {
            const row = (cdt && cdn && locals[cdt] && locals[cdt][cdn]) || doc;
            const wh = row[wh_field];
            if (!wh) {
                frappe.show_alert({
                    message: __("กรุณาเลือก {0} ก่อน", [__(frappe.meta.get_label(row.doctype, wh_field))]),
                    indicator: "orange",
                });
                return { filters: { name: "__no_shelf__" } };
            }
            return { filters: { warehouse: wh } };
        };
    }

    // เมื่อเปลี่ยนคลัง ให้ล้างค่าชั้นวางถ้าชั้นนั้นไม่ได้อยู่ในคลังใหม่
    async function clear_shelf_if_mismatch(cdt, cdn, wh_field, shelf_field) {
        const row = locals[cdt] && locals[cdt][cdn];
        if (!row || !row[shelf_field]) return;

        const shelf = row[shelf_field];
        const wh = row[wh_field];
        let shelf_wh = null;
        if (wh) {
            const r = await frappe.db.get_value("Shelf", shelf, "warehouse");
            shelf_wh = r.message && r.message.warehouse;
        }

        if (!wh || shelf_wh !== wh) {
            await frappe.model.set_value(cdt, cdn, shelf_field, null);
            const where = row.idx && row.parentfield ? __("แถวที่ {0}: ", [row.idx]) : "";
            frappe.show_alert({
                message: where + __("ล้างค่าชั้น {0} เพราะไม่ได้อยู่ในคลังที่เลือก", [shelf]),
                indicator: "blue",
            });
        }
    }

    // Child DocType -> { ฟิลด์คลัง: Set(ฟิลด์ชั้นวาง) }
    // Packed Item ถูกใช้ร่วมกันหลายเอกสาร จึงรวมไว้ที่เดียวเพื่อไม่ให้ handler ซ้ำ
    const child_events = {};

    Object.entries(SHELF_FIELD_MAP).forEach(([doctype, rules]) => {
        const setup_queries = (frm) => {
            rules.forEach(([table, , wh_field, shelf_field]) => {
                if (table) {
                    if (frm.fields_dict[table]) {
                        frm.set_query(shelf_field, table, shelf_query(wh_field));
                    }
                } else if (frm.fields_dict[shelf_field]) {
                    frm.set_query(shelf_field, shelf_query(wh_field));
                }
            });
        };

        const parent_events = { setup: setup_queries, refresh: setup_queries };

        rules.forEach(([table, child, wh_field, shelf_field]) => {
            if (table) {
                child_events[child] = child_events[child] || {};
                child_events[child][wh_field] = child_events[child][wh_field] || new Set();
                child_events[child][wh_field].add(shelf_field);
            } else {
                parent_events[wh_field] = (frm) =>
                    clear_shelf_if_mismatch(frm.doctype, frm.docname, wh_field, shelf_field);
            }
        });

        frappe.ui.form.on(doctype, parent_events);
    });

    Object.entries(child_events).forEach(([child, fields]) => {
        const events = {};
        Object.entries(fields).forEach(([wh_field, shelf_fields]) => {
            events[wh_field] = (frm, cdt, cdn) => {
                shelf_fields.forEach((sf) => clear_shelf_if_mismatch(cdt, cdn, wh_field, sf));
            };
        });
        frappe.ui.form.on(child, events);
    });
})();