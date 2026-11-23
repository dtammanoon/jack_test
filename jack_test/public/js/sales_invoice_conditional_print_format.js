// Select the appropriate Print Format for Sales Invoice.
frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        frm.__conditional_print_format = frm.doc.is_return
            ? "Sales Invoice Thai Full Tax Credit Note"
            : "Sales Invoice Thai Full Tax Invoice";
    }
});
