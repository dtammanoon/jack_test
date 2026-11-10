
frappe.query_reports["Serial Cost Grade Traceability"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "item_code",
            label: __("Item Code"),
            fieldtype: "Link",
            options: "Item",
            reqd: 0
        },
        {
            fieldname: "serial_no",
            label: __("Serial No"),
            fieldtype: "MultiSelectList",
            options: "Serial No",
            reqd: 0,
            get_data: function(txt) {
                return frappe.db.get_link_options("Serial No", txt);
            }
        }
    ]
};
