frappe.listview_settings['Book'] = {
    // 1. ซ่อนคอลัมน์ ID ในตารางหลัก
    hide_name_column: true, 

    onload: function(listview) {
        // 2. ซ่อนปุ่ม Filter ID และแถบกรองตัวแปร name
        listview.page.wrapper.find('.list-row-filterable[data-fieldname="name"]').hide();
        listview.page.wrapper.find('div[data-fieldname="name"]').hide();
    },

    refresh: function(listview) {
        // ทำซ้ำในจังหวะ refresh เพื่อป้องกันปุ่มเด้งกลับมา
        listview.page.wrapper.find('.list-row-filterable[data-fieldname="name"]').hide();
        listview.page.wrapper.find('div[data-fieldname="name"]').hide();
    }
};