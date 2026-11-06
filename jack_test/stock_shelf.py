import frappe
from frappe import _

SHELF_DOCTYPE = "Shelf"

# DocType -> [(ตารางลูก หรือ None ถ้าเป็นหัวเอกสาร, ฟิลด์คลัง, ฟิลด์ชั้นวาง)]
SHELF_FIELD_MAP = {
    "Stock Entry": [
        ("items", "s_warehouse", "shelf"),
        ("items", "t_warehouse", "to_shelf"),
    ],
    "Purchase Receipt": [
        ("items", "warehouse", "shelf"),
        ("items", "from_warehouse", "from_shelf"),
    ],
    "Purchase Invoice": [
        ("items", "warehouse", "shelf"),
        ("items", "from_warehouse", "from_shelf"),
    ],
    "Delivery Note": [
        ("items", "warehouse", "shelf"),
        ("items", "target_warehouse", "to_shelf"),
        ("packed_items", "warehouse", "shelf"),
    ],
    "Sales Invoice": [
        ("items", "warehouse", "shelf"),
        ("items", "target_warehouse", "to_shelf"),
        ("packed_items", "warehouse", "shelf"),
    ],
    "POS Invoice": [
        ("items", "warehouse", "shelf"),
        ("packed_items", "warehouse", "shelf"),
    ],
    "Stock Reconciliation": [
        ("items", "warehouse", "shelf"),
    ],
    "Pick List": [
        ("locations", "warehouse", "shelf"),
    ],
    "Subcontracting Receipt": [
        ("items", "warehouse", "shelf"),
    ],
    "Putaway Rule": [
        (None, "warehouse", "shelf"),
    ],
}


def validate_shelf(doc, method=None):
    """ตรวจว่าชั้นวางที่เลือกอยู่ในคลังเดียวกับที่ระบุในแถวนั้น"""
    rules = SHELF_FIELD_MAP.get(doc.doctype)
    if not rules:
        return

    # รวบรวมทุกแถวที่มีการระบุชั้นวาง
    entries = []
    for table, wh_field, shelf_field in rules:
        rows = (doc.get(table) or []) if table else [doc]
        for row in rows:
            shelf = row.get(shelf_field)
            if shelf:
                entries.append((row, table, wh_field, shelf_field, shelf))

    if not entries:
        return

    # ดึงคลังของทุกชั้นด้วย query เดียว
    shelf_names = list({e[4] for e in entries})
    shelf_wh = dict(
        frappe.get_all(
            SHELF_DOCTYPE,
            filters={"name": ["in", shelf_names]},
            fields=["name", "warehouse"],
            as_list=True,
        )
    )

    errors = []
    for row, table, wh_field, shelf_field, shelf in entries:
        wh = row.get(wh_field)
        if table:
            where = _("{0} แถวที่ {1}").format(_(doc.meta.get_label(table)), row.idx)
        else:
            where = _("หัวเอกสาร")
        shelf_label = _(row.meta.get_label(shelf_field))
        wh_label = _(row.meta.get_label(wh_field))

        if shelf not in shelf_wh:
            errors.append(_("{0}: ไม่พบชั้น {1}").format(where, frappe.bold(shelf)))
        elif not wh:
            errors.append(
                _("{0}: ระบุ {1} = {2} แต่ยังไม่ได้เลือก {3}").format(
                    where, shelf_label, frappe.bold(shelf), wh_label
                )
            )
        elif shelf_wh[shelf] != wh:
            errors.append(
                _("{0}: ชั้น {1} อยู่ในคลัง {2} ไม่ตรงกับ {3} ({4})").format(
                    where, frappe.bold(shelf), frappe.bold(shelf_wh[shelf]), wh_label, frappe.bold(wh)
                )
            )

    if errors:
        frappe.throw("<br>".join(errors), title=_("ชั้นวางไม่ตรงกับคลัง"))