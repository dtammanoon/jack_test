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
// ส่วนที่ 2: หลังบันทึก Session Defaults ให้กลับ Desktop (/apps) แบบเสถียร
// =========================================================
(() => {
    const FLAG_KEY = "jack_test_redirect_to_apps";
    const TARGET_PATH = "/apps";

    // 2.1 ตรวจตอนโหลดหน้า: ถ้ามี flag ค้างจากการบันทึก Session Defaults ให้ไป /apps
    //     (ทำงานทันทีที่ไฟล์โหลด ไม่ต้องรอ document.ready ลดการเห็นหน้าเดิมแวบหนึ่ง)
    try {
        if (sessionStorage.getItem(FLAG_KEY)) {
            sessionStorage.removeItem(FLAG_KEY);
            if (window.location.pathname.replace(/\/+$/, "") !== TARGET_PATH) {
                window.location.replace(window.location.origin + TARGET_PATH);
                return; // หยุด ไม่ต้องผูก event ต่อ เพราะกำลังเปลี่ยนหน้า
            }
        }
    } catch (e) {
        console.warn("[Jack Test] sessionStorage unavailable", e);
    }

    // 2.2 ดักจับ API บันทึก Session Defaults
    $(document).ajaxSuccess(function (event, xhr, settings) {
        const url = settings && settings.url ? settings.url : "";
        if (!url.includes("set_session_default_values")) return;

        // บันทึกจริงสำเร็จเท่านั้น (Frappe ส่ง message = "success")
        const msg = xhr.responseJSON && xhr.responseJSON.message;
        if (msg && msg !== "success") return;

        // ฝาก flag ไว้ก่อน ไม่ว่า Frappe จะ reload หรือไม่ หน้าถัดไปจะพาไป /apps เอง
        try {
            sessionStorage.setItem(FLAG_KEY, "1");
        } catch (e) {}

        // Fallback: ถ้าเวอร์ชันไหนไม่ได้สั่ง reload เลย ให้ไปเองหลังรอพอสมควร
        // (ถ้า reload เกิดก่อน timer นี้จะถูกยกเลิกไปเอง ไม่มีผลเสีย)
        setTimeout(() => {
            window.location.assign(window.location.origin + TARGET_PATH);
        }, 2000);
    });
})();
