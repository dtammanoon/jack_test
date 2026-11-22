// Select the document-specific Print Format in Frappe Print Preview.
(() => {
    const PrintView = frappe.ui?.form?.PrintView;

    if (!PrintView) {
        console.error(
            "POS Full Tax Invoice: Frappe PrintView is not available."
        );
        return;
    }

    if (PrintView.prototype.__conditional_format_patched) {
        return;
    }

    PrintView.prototype.__conditional_format_patched = true;

    const original = PrintView.prototype.set_default_print_format;

    PrintView.prototype.set_default_print_format = function () {
        const desired = this.frm?.__conditional_print_format;

        if (
            desired &&
            frappe.meta
                .get_print_formats(this.frm.doctype)
                .includes(desired)
        ) {
            this.set_print_format_value(desired);
            return;
        }

        return original.call(this);
    };
})();
