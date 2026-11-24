import frappe
from frappe.utils import cint
from frappe.core.doctype.session_default_settings.session_default_settings import (
    set_session_default_values as core_set_session_default_values,
)

DT = "Session Default Selected"
KEYS = ("company", "branch", "cost_center")


@frappe.whitelist()
def set_session_default_values(default_values, jack_silent_sync=None):
    """Override ของ core: ตั้งค่า Session Defaults ตามปกติ
    และถ้าผู้ใช้เลือกเองจากกล่อง Session Defaults (ไม่ใช่ auto-sync) ให้บันทึกลง Session Default Selected"""
    result = core_set_session_default_values(default_values)

    if result == "success" and not cint(jack_silent_sync):
        save_selected(frappe.parse_json(default_values))

    return result


def save_selected(values):
    user = frappe.session.user
    if user == "Guest":
        return

    if frappe.db.exists(DT, user):
        doc = frappe.get_doc(DT, user)
    else:
        doc = frappe.new_doc(DT)
        doc.user = user

    for key in KEYS:
        if key in values:
            doc.set(key, values.get(key) or None)

    doc.save(ignore_permissions=True)


@frappe.whitelist()
def get_selected():
    """คืนค่าที่ผู้ใช้เลือกไว้ล่าสุด"""
    user = frappe.session.user
    if not frappe.db.exists(DT, user):
        return {}

    row = frappe.db.get_value(DT, user, list(KEYS), as_dict=True) or {}
    return {k: v for k, v in row.items() if v}