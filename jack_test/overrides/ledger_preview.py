import frappe
from frappe import _
from erpnext.controllers import stock_controller


@frappe.whitelist()
def show_accounting_ledger_preview(company, doctype, docname):
    captured = {"entries": None}
    has_branch = frappe.get_meta("GL Entry").has_field("branch")

    original_get_entries = stock_controller.get_gl_entries_for_preview

    def get_entries_with_branch(*args, **kwargs):
        # ดึง GL Entry อีกชุดที่มี branch เก็บไว้ก่อนถูก rollback
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
                captured["entries"] = [branch_map.get(e.get("name")) for e in entries]
            else:
                # กรณีไม่มี name ให้ดึงใหม่พร้อม branch ตามลำดับเดิม
                fields = list(args[2] if len(args) > 2 else kwargs.get("fields", []))
                captured["entries"] = [
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
    add_account_name(columns, data)
    add_branch(columns, data, captured["entries"])
    return result


def find_index(labels, label):
    for lb in (_(label), label):
        if lb in labels:
            return labels.index(lb)
    return None


def add_account_name(columns, data):
    if not columns or data is None:
        return
    labels = [c.get("name") for c in columns]
    if _("Account Name") in labels:
        return
    idx = find_index(labels, "Account")
    if idx is None:
        return

    accounts = {row[idx] for row in data if len(row) > idx and row[idx]}
    account_map = {}
    if accounts:
        account_map = dict(frappe.get_all(
            "Account",
            filters={"name": ["in", list(accounts)]},
            fields=["name", "account_name"],
            as_list=True,
        ))

    columns.insert(idx + 1, {
        "name": _("Account Name"), "editable": False, "width": 180, "align": "left",
    })
    for row in data:
        account = row[idx] if len(row) > idx else ""
        row.insert(idx + 1, account_map.get(account, ""))


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
        "name": _("Branch"), "editable": False, "width": 150, "align": "left",
    })
    for row, branch in zip(data, branches):
        row.insert(idx + 1, branch or "")