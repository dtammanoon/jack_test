# ไฟล์นี้ใช้สำหรับเปลี่ยนชื่อ Item Code และ Item Name ของสินค้าที่เป็น Variant
# อยู่ในไฟล์ CSV ที่กำหนด โดยมีคอลัมน์ดังนี้:   
# Item Code,Item Name,New Item Code,New Item Name
# ตัวอย่าง CSV: example/Item Comp.csv
# Copy file ไปที่ frappe-bench/sites/<your-site>/private/files/Item Comp.csv

# # ทดสอบก่อน (dry run)
# bench --site replay.local execute jack_test.rename_variant_items.execute --kwargs "{'file': 'Item Comp.csv', 'dry_run': 1}"

# # รันจริง
# bench --site replay.local execute jack_test.rename_variant_items.execute --kwargs "{'file': 'Item Comp.csv', 'dry_run': 0}"

# # ล้าง cache
# bench --site replay.local clear-cache

import csv
import os
import frappe
from frappe.model.rename_doc import rename_doc


def resolve_path(file):
    """หา path จริงของไฟล์ CSV"""
    if not file:
        frappe.throw("กรุณาระบุชื่อไฟล์ เช่น file='Item Comp.csv'")

    # 1) path เต็มที่มีไฟล์อยู่จริง
    if os.path.isabs(file) and os.path.exists(file):
        return file

    # 2) path นับจาก folder ของ site / private/files / public/files
    f = file.lstrip("/")
    if f.startswith("files/"):          # URL ของไฟล์ public เช่น /files/xxx.csv
        f = "public/" + f

    candidates = [
        frappe.get_site_path(f),
        frappe.get_site_path("private", "files", f),
        frappe.get_site_path("public", "files", f),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    frappe.throw("ไม่พบไฟล์: {0}<br>ค้นหาใน:<br>{1}".format(file, "<br>".join(candidates)))


def get_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:   # utf-8-sig ตัด BOM ที่ Excel ใส่มา
        reader = csv.DictReader(f)
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in reader]


def update_item_name(item_code, new_name):
    """เปลี่ยน Item Name ทั้งใน Item และ Item Price"""
    frappe.db.set_value("Item", item_code, "item_name", new_name)
    frappe.db.sql(
        "update `tabItem Price` set item_name=%s where item_code=%s",
        (new_name, item_code),
    )


def execute(file=None, dry_run=1):
    """
    file     -> ชื่อไฟล์ CSV หรือ path
    dry_run=1  -> ตรวจสอบอย่างเดียว ไม่แก้ข้อมูล
    dry_run=0  -> เปลี่ยนชื่อจริง
    """
    dry_run = int(dry_run)
    path = resolve_path(file)
    rows = get_rows(path)

    # ตรวจหัวคอลัมน์
    required = {"Item Code", "New Item Code", "New Item Name"}
    missing = required - set(rows[0].keys()) if rows else required
    if missing:
        frappe.throw(f"ไฟล์ขาดคอลัมน์: {', '.join(sorted(missing))}")

    print(f"File    : {path}")
    print(f"Rows    : {len(rows)}\n")

    ok, skipped, failed = 0, 0, []

    for i, r in enumerate(rows, start=1):
        old_code = r.get("Item Code")
        new_code = r.get("New Item Code")
        new_name = r.get("New Item Name")

        if not old_code or not new_code:
            print(f"[{i}] SKIP: ข้อมูลไม่ครบ {r}")
            skipped += 1
            continue

        # รันซ้ำได้: ถ้าเปลี่ยนไปแล้วก็แค่อัปเดตชื่อ
        if not frappe.db.exists("Item", old_code):
            if frappe.db.exists("Item", new_code):
                print(f"[{i}] ALREADY RENAMED: {old_code} -> {new_code}")
                if not dry_run and new_name:
                    update_item_name(new_code, new_name)
                    frappe.db.commit()
                skipped += 1
            else:
                print(f"[{i}] NOT FOUND: {old_code}")
                failed.append((old_code, "Item not found"))
            continue

        if old_code != new_code and frappe.db.exists("Item", new_code):
            print(f"[{i}] CONFLICT: {new_code} มีอยู่แล้ว")
            failed.append((old_code, f"{new_code} already exists"))
            continue

        variant_of = frappe.db.get_value("Item", old_code, "variant_of")
        print(f"[{i}] {old_code} -> {new_code} | name: {new_name} | variant_of: {variant_of or '-'}")

        if dry_run:
            continue

        try:
            # 1) เปลี่ยน Item Code (แก้ Link ทุกที่ให้ด้วย)
            if old_code != new_code:
                rename_doc("Item", old_code, new_code, force=True, merge=False, show_alert=False)

            # 2) เปลี่ยน Item Name + Item Price
            if new_name:
                update_item_name(new_code, new_name)

            frappe.db.commit()
            ok += 1
        except Exception as e:
            frappe.db.rollback()
            failed.append((old_code, str(e)))
            print(f"    ERROR: {e}")

    print("\n===== SUMMARY =====")
    print(f"Mode    : {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"Success : {ok}")
    print(f"Skipped : {skipped}")
    print(f"Failed  : {len(failed)}")
    for code, err in failed:
        print(f"  - {code}: {err}")