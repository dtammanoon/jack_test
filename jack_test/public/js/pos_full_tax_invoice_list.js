frappe.listview_settings["POS Full Tax Invoice"] = {
    onload(listview) {
        const sort_by = "name";
        const sort_order = "desc";

        // Update the actual Sort Selector used by get_args()
        listview.sort_selector.set_value(sort_by, sort_order);

        // Update ListView state and trigger refresh
        listview.on_sort_change(sort_by, sort_order);
    },
};
