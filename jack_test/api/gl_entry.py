import frappe

def force_branch_dimension(doc, method):
    # ตรวจสอบว่าผู้ใช้งานที่กำลังกดบันทึกเอกสารมีค่าสาขาประจำตัวเป็นอะไร
    user_branch = frappe.defaults.get_user_default("branch")
    if user_branch:
        # สั่งบังคับเปลี่ยนฟิลด์ branch ในบรรทัดสมุดบัญชีแยกประเภทใบนี้ให้กลายเป็นสาขาของผู้ใช้โดยเด็ดขาด 
        doc.branch = user_branch
