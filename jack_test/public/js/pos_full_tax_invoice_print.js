
frappe.ui.form.on("POS Full Tax Invoice", {
    onload(frm) {
        // Prevent wrapping the standard print method more than once.
        if (frm.__conditional_print_format_patched) {
            return;
        }

        frm.__conditional_print_format_patched = true;

        const original_print_doc = frm.print_doc.bind(frm);

        frm.print_doc = function () {
            const print_format =
                frm.doc.document_type === "Full Tax Credit Note"
                    ? "POS Full Tax Credit Note"
                    : "POS Full Tax Invoice";

            // Pass the desired format to the Print Preview page.
            frm.__conditional_print_format = print_format;

            // Use a per-form Meta copy. Do not modify shared DocType Meta.
            frm.meta = {
                ...frm.meta,
                default_print_format: print_format,
            };

            // Keep Frappe's standard print flow and unsaved-change warning.
            original_print_doc();
        };
    },
});
