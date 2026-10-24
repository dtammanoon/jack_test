"""
import frappe

# === คงฟังก์ชันจัดระเบียบแผงไอคอน clean_apps_screen ด้านบนไว้ตามปกติ ===

def force_redirect_after_save(doc, method=None):
   
    # ตรวจเช็กเงื่อนไข: ถ้าเป็นการยิงคำสั่งเซฟบันทึกค่าเริ่มต้น (Session Defaults) จากหน้าต่างป็อปอัปหน้าร้านจริง
    if frappe.local.form_dict.get("cmd") == "frappe.core.doctype.user.user.set_defaults":
        
        print("=========================================================")
        print(f"[Jack Test Event] 🎯 ดักจับคำสั่งบันทึกสิทธิ์สำเร็จสำหรับผู้ใช้: {doc.name}")
        print("=========================================================")
        
        # ล้างหน่วยความจำค้างเพื่อให้สิทธิ์สาขาพระราม 9 เริ่มมีผลคำนวณบัญชีและคลัง
        frappe.cache.hdel("bootinfo", doc.name)
        
        # สั่งดีดหน้าจอพนักงานระดับโครงสร้างระบบ บังคับเปลี่ยนเส้นทางเว็บเบราว์เซอร์กลับไปที่ /apps ทันที
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/apps"
"""