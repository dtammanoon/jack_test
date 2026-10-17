import frappe

def set_branch_from_pos_profile(doc, method=None):
    """
    ฟังก์ชันทำงานตอน before_save ของ POS Invoice:
    จะดึง Branch จาก POS Profile มาใส่ทั้งตัวบิล (Header) และรายการสินค้า (Items)
    """
    user = frappe.session.user
    
    # 1. ค้นหา POS Profile ของ User รายนี้
    pos_profile = frappe.db.get_value("POS Profile", {"user": user, "disabled": 0}, "name")
    if not pos_profile:
        pos_profile = frappe.db.get_value("POS Profile User", {"user": user}, "parent")

    # 2. ถ้าเจอ POS Profile ให้ดึงค่า Branch ออกมา
    if pos_profile:
        branch = frappe.db.get_value("POS Profile", pos_profile, "branch")
        
        if branch:
            # 3. ใส่ Branch ที่ตัวหัวบิล (Header) - เฉพาะกรณีที่ยังไม่มีการระบุค่าไว้
            if not doc.get("branch"):
                doc.branch = branch
            
            # 4. วนลูปเพื่อใส่ Branch ให้กับสินค้าทุกชิ้นในตาราง (Child Table)
            # โน้ต: ต้องแน่ใจว่าใน Doctype 'POS Invoice Item' มีฟิลด์ชื่อ 'branch' รองรับไว้แล้ว
            if doc.get("items"):
                for item in doc.items:
                    if not item.get("branch"):
                        item.branch = branch
