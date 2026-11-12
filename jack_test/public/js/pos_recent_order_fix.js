
(() => {
    const PAGE_NAME = "point-of-sale";
    const patchedInstances = new WeakSet();

    function patchPOS(pos) {
        if (
            !pos ||
            !pos.recent_order_list ||
            !pos.recent_order_list.events ||
            !pos.order_summary
        ) {
            return false;
        }

        if (patchedInstances.has(pos)) {
            return true;
        }

        const list = pos.recent_order_list;
        const originalOpen = list.events.open_invoice_data;

        list.events.open_invoice_data = (doctype, name) => {
            if (!["POS Invoice", "Sales Invoice"].includes(doctype)) {
                return originalOpen?.(doctype, name);
            }

            frappe.db.get_doc(doctype, name)
                .then(doc => {
                    pos.order_summary.load_summary_of(doc);
                    pos.order_summary.toggle_component(true);
                })
                .catch(() => {
                    frappe.msgprint(
                        __("Unable to load the selected invoice.")
                    );
                });
        };

        patchedInstances.add(pos);
        return true;
    }

    function waitForPOS(previousPOS = null) {
        let attempts = 0;

        const timer = window.setInterval(() => {
            attempts++;

            const pos = window.cur_pos;

            if (pos && pos !== previousPOS && patchPOS(pos)) {
                window.clearInterval(timer);
                return;
            }

            if (pos && patchedInstances.has(pos)) {
                window.clearInterval(timer);
                return;
            }

            if (attempts >= 50) {
                window.clearInterval(timer);
            }
        }, 200);
    }

    function isPOSPage() {
        return (frappe.get_route() || []).includes(PAGE_NAME);
    }

    if (isPOSPage()) {
        if (!patchPOS(window.cur_pos)) {
            waitForPOS();
        }
    }

    if (
        frappe.router &&
        !window.__jack_test_pos_recent_order_listener
    ) {
        window.__jack_test_pos_recent_order_listener = true;

        frappe.router.on("change", () => {
            if (!isPOSPage()) return;

            const previousPOS = window.cur_pos;

            if (!patchPOS(previousPOS)) {
                waitForPOS(previousPOS);
            }
        });
    }
})();
