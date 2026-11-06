{% include "erpnext/accounts/report/gross_profit/gross_profit.js" %}

(() => {
    const base = frappe.query_reports["Gross Profit"];
    const base_filters = base.filters || [];

    // const item_filter = {
    //     fieldname: "item_code",
    //     label: __("Item Code"),
    //     fieldtype: "Link",
    //     options: "Item",
    // };

	const item_filter = {
		fieldname: "item_code",
		label: __("Item Code"),
		fieldtype: "MultiSelectList",
		get_data: (txt) => frappe.db.get_link_options("Item", txt),
	};

    const filters = [];
    base_filters.forEach((f) => {
        if (f.fieldname === "group_by") {
            // ใส่ Item Code แทนที่ตำแหน่ง Group By
            // (ถ้า ERPNext เวอร์ชันใหม่มี item_code อยู่แล้ว จะไม่ใส่ซ้ำ)
            if (!base_filters.some((x) => x.fieldname === "item_code")) {
                filters.push(item_filter);
            }
            return;
        }
        filters.push(Object.assign({}, f));
    });

    frappe.query_reports["Gross Profit Chart"] = { filters };

    if (erpnext?.utils?.add_dimensions) {
        erpnext.utils.add_dimensions("Gross Profit Chart", 15);
    }
})();