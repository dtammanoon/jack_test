import frappe
from frappe import _
from erpnext.controllers import stock_controller

# ปรับความกว้างคอลัมน์ Account ได้ที่นี่
ACCOUNT_COLUMN_WIDTH = 200
BRANCH_COLUMN_WIDTH = 110


@frappe.whitelist()
def show_accounting_ledger_preview(company, doctype, docname):
    captured = {"branches": None}
    has_branch = frappe.get_meta("GL Entry").has_field("branch")

    original_get_entries = stock_controller.get_gl_entries_for_preview

    def get_entries_with_branch(*args, **kwargs):
        # ดึง branch เก็บไว้ก่อน GL Entry ชั่วคราวถูก rollback
        entries = original_get_entries(*args, **kwargs)
        if has_branch and entries:
            names = [e.get("name") for e in entries if e.get("name")]
            if names:
                branch_map = dict(frappe.get_all(
                    "GL Entry",
                    filters={"name": ["in", names]},
                    fields=["name", "branch"],
                    as_list=True,
                ))
                captured["branches"] = [branch_map.get(e.get("name")) for e in entries]
            else:
                fields = list(args[2] if len(args) > 2 else kwargs.get("fields", []))
                captured["branches"] = [
                    e.get("branch") for e in original_get_entries(
                        args[0], args[1], fields + ["branch"]
                    )
                ]
        return entries

    stock_controller.get_gl_entries_for_preview = get_entries_with_branch
    try:
        result = stock_controller.show_accounting_ledger_preview(company, doctype, docname)
    finally:
        # คืนค่า function เดิมเสมอ
        stock_controller.get_gl_entries_for_preview = original_get_entries

    columns, data = result.get("gl_columns"), result.get("gl_data")
    widen_account_column(columns)
    add_branch(columns, data, captured["branches"])
    return result


def find_index(labels, label):
    for lb in (_(label), label):
        if lb in labels:
            return labels.index(lb)
    return None


def widen_account_column(columns):
    if not columns:
        return
    labels = [c.get("name") for c in columns]
    idx = find_index(labels, "Account")
    if idx is not None:
        columns[idx]["width"] = ACCOUNT_COLUMN_WIDTH


def add_branch(columns, data, branches):
    if not columns or data is None or branches is None:
        return
    # จำนวนแถวต้องตรงกัน ไม่งั้นข้อมูลจะเลื่อนผิดแถว
    if len(branches) != len(data):
        return
    labels = [c.get("name") for c in columns]
    if _("Branch") in labels:
        return
    idx = find_index(labels, "Party")
    if idx is None:
        return

    columns.insert(idx + 1, {
        "name": _("Branch"),
        "editable": False,
        "width": BRANCH_COLUMN_WIDTH,
        "align": "left",
    })
    for row, branch in zip(data, branches):
        row.insert(idx + 1, branch or "")