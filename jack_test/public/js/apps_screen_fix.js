// =========================================================
// ส่วนที่ 1: บังคับวาดไอคอน POS ขึ้นหน้าจอเดสก์ท็อปหลัก
// =========================================================
(() => {
    if (!window.frappe || !frappe.boot) return;

    const boot = frappe.boot;
    const appsData = boot.apps_data?.apps;
    const appData = boot.app_data;

    if (!Array.isArray(appsData) || !Array.isArray(appData)) {
        return;
    }

    const pos = appsData.find(app => app.title === "POS");
    if (pos && !appData.some(app => app.app_name === "jack_test_pos_tile")) {
        appData.push({
            app_name: "jack_test_pos_tile",
            app_title: "POS",
            on_apps_screen: true,
            sequence_id: 150,
            app_route: "/desk/stock/point-of-sale",
            desk_route: "",
            app_logo_url: "/assets/jack_test/images/pos.png",
            dock: []
        });
    }
})();

// =========================================================
// ส่วนที่ 2: ดักจับคำสั่ง API บันทึก Session Defaults โดยตรง เพื่อดีดกลับ Desktop
// =========================================================
$(document).ready(function() {
    //console.warn("=========================================================");
    //console.warn("[Jack Test] 🛰️ Debug Ajax 2");
    //console.warn("=========================================================");     
    // ใช้ ajaxSuccess เพื่อจับสัญญานเครือข่ายหลังจากระบบบันทึกข้อมูลสาขาสำเร็จ
    $(document).ajaxSuccess(function(event, xhr, settings) {
        
        // 1. เจาะจงตรวจเซ็กว่า API ตัวที่ส่งสำเร็จ คือตัวบันทึกค่า Defaults ของระบบ Frappe ใช่ไหม
        let isSetDefaultsApi = settings.url && settings.url.includes('set_session_default_values');

        //console.warn("settings.url :", settings.url);
        //console.warn("settings.url.includes :", settings.url.includes('set_session_default_values'));

        //debugger; 

        // 2. ถ้าใช่คำสั่งบันทึกสาขาชัวร์ๆ ให้ทำตามแผนทันที
        if (isSetDefaultsApi) {
            
            // หน่วงเวลาสั้นๆ 0.4 วินาที เพื่อให้ระบบหลังบ้านจัดการ Session เรียบร้อย
            setTimeout(() => {
                let target_apps_url = window.location.origin + '/apps';
                window.location.assign(target_apps_url);
            }, 400);
        }
    });
});

