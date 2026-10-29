import frappe
from frappe import _


def apply_patch():
    """แทนที่ execute ของ General Ledger ด้วยเวอร์ชันที่เพิ่มคอลัมน์ Account Name"""
    from erpnext.accounts.report.general_ledger import general_ledger as gl

    # กัน patch ซ้ำ (ถ้าซ้ำจะเรียกตัวเองวนไม่รู้จบ)
    if getattr(gl.execute, "_jack_patched", False):
        return

    original_execute = gl.execute

    def execute(filters=None):
        result = list(original_execute(filters))
        columns, data = result[0], result[1]

        add_account_name_column(columns)
        fill_account_name(data)

        result[0], result[1] = columns, data
        return tuple(result)

    execute._jack_patched = True
    gl.execute = execute


def add_account_name_column(columns):
    if not columns:
        return

    fieldnames = [c.get("fieldname") if isinstance(c, dict) else None for c in columns]
    if "account_name" in fieldnames or "account" not in fieldnames:
        return

    idx = fieldnames.index("account")
    columns.insert(idx + 1, {
        "label": _("Account Name"),
        "fieldname": "account_name",
        "fieldtype": "Data",
        "width": 180,
        "align": "left",
    })


def fill_account_name(data):
    if not data:
        return

    # ดึงเฉพาะ Account ที่มีในรายงาน แล้ว query ครั้งเดียว
    accounts = {
        row.get("account") for row in data
        if isinstance(row, dict) and row.get("account")
    }
    if not accounts:
        return

    account_map = dict(frappe.get_all(
        "Account",
        filters={"name": ["in", list(accounts)]},
        fields=["name", "account_name"],
        as_list=True,
    ))

    for row in data:
        if isinstance(row, dict) and row.get("account"):
            # แถว Opening / Total / Closing ไม่ตรงกับ Account จริง จึงได้ค่าว่าง
            row["account_name"] = account_map.get(row["account"], "")