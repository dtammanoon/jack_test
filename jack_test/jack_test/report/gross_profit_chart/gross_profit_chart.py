import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.gross_profit.gross_profit import execute as gross_profit_execute


def execute(filters=None):
    filters = frappe._dict(filters or {})
    filters.group_by = "Item Code"  # ล็อกไว้
    key = "item_code"

    # ดึง item_code ออกมากรองเอง ไม่ส่งต่อให้รายงานต้นฉบับ
    item_codes = _to_set(filters.pop("item_code", None))

    result = gross_profit_execute(frappe._dict(filters))
    columns, data = result[0], result[1]

    fieldnames = [_get_fieldname(c) for c in columns]
    total_labels = {"Total", _("Total")}

    out = []
    for row in data:
        if isinstance(row, (list, tuple)):
            row = frappe._dict(zip(fieldnames, row))
        else:
            row = frappe._dict(row)

        val = row.get(key)

        # ตัดแถวค่าว่าง (แท่ง None) และแถว Total
        if not val or str(val).strip("'\" ") in total_labels:
            continue

        # ตัดแถวย่อยที่ซ้อนอยู่
        if flt(row.get("indent")) > 0:
            continue

        # กรองตาม Item Code ที่เลือก
        if item_codes and val not in item_codes:
            continue

        out.append(row)

    return columns, out


def _to_set(value):
    """รับได้ทั้ง 'ITEM-01', ['ITEM-01','ITEM-02'] และ '["ITEM-01","ITEM-02"]'"""
    if not value:
        return set()
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("["):
            value = frappe.parse_json(value)
        else:
            value = [value]
    return {v for v in value if v}


def _get_fieldname(col):
    if isinstance(col, str):
        return frappe.scrub(col.split(":")[0])
    return col.get("fieldname")