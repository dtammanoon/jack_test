app_name = "jack_test"
app_title = "Jack Test"
app_publisher = "Tammanoon Deeying"
app_description = "Jack Test"
app_email = "dtammanoon@gmail.com"
app_license = "mit"

# ให้มีชุดนี้ชุดเดียว และลบชุดที่ประกาศซ้ำด้านล่างทิ้งให้หมดครับ
add_to_apps_screen = [
    {
        "name": "select_branch",
        "logo": "/assets/jack_test/images/branch.png", 
        "title": "Branch",
        "route": "/app/workspace/Home?action=select_branch", # ชี้กลับมาหน้าแรกเพื่อไม่ให้ Not Found และส่งพารามิเตอร์ไปดักจับ
        "is_query_link": True        
    },
    {
        "name": "sale",
        "logo": "/assets/jack_test/images/pos.png", 
        "title": "POS",
        "route": "/desk/stock/point-of-sale",
        "is_query_link": True
    }    
]


fixtures = [
    {
        "dt": "Server Script",
        "filters": [["module", "=", "Jack Test"]] # เปลี่ยนจาก "-" เป็น "="
    },
    {
        "dt": "Client Script",
        "filters": [["module", "=", "Jack Test"]] # เปลี่ยนจาก "-" เป็น "="
    }
]

doc_events = {
    "Book Order": {
        "before_save": "jack_test.jack_test.doctype.book_order.book_order.compute_total",
        "before_submit": "jack_test.jack_test.doctype.book_order.book_order.confirm_date",
        "on_submit": "jack_test.jack_test.doctype.book_order.book_order.update_ordered_qty",
        "on_cancel": "jack_test.jack_test.doctype.book_order.book_order.update_ordered_qty",
    }       
}

# แก้ไขเพิ่มในไฟล์ hooks.py ครับคุณแจ็ก

# ผูกเรื่องให้ระบบแผงไอคอนเรียกใช้งานฟังก์ชันจัดกระดานไอคอน (ทำตามขั้นตอนเดิม)
# extend_bootinfo = "jack_test.api.clean_apps_screen"

app_include_js = "/assets/jack_test/js/apps_screen_fix.js"

# บังคับลบหรือปิดฟังก์ชันนี้ออกจากระบบ Global Request เพื่อหยุดการรันมั่วซั่วทุกหน้าจอครับ
# before_request = ["jack_test.api.force_redirect_after_save"]

# หรือปล่อยว่างไว้แบบนี้
# before_request = []

# override_whitelisted_methods = {}

# ส่วนสำคัญ (เพิ่มช่องทางดักกระแสไฟ): สั่งให้ระบบวิ่งมาตรวจเช็กฟังก์ชันดีดหน้าจอของเราทุกครั้งที่มีการยิงคำสั่งในระบบ
# on_session_expiry = "jack_test.api.force_redirect_after_save"
# before_request = ["jack_test.api.force_redirect_after_save"]

# แก้ไขบรรทัดนี้ใน hooks.py ให้ตรงตามฟังก์ชันที่มีอยู่จริง
# boot_session = "jack_test.api.set_session_defaults"


# เพิ่มต่อท้ายไฟล์ hooks.py เดิมของคุณ
#doc_events = {
#    "POS Invoice": {
#        "before_save": "jack_test.api.pos_invoice.set_branch_from_pos_profile"
#    }
#}

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "jack_test",
# 		"logo": "/assets/jack_test/logo.png",
# 		"title": "Jack Test",
# 		"route": "/jack_test",
# 		"has_permission": "jack_test.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/jack_test/css/jack_test.css"
# app_include_js = "/assets/jack_test/js/jack_test.js"

# include js, css files in header of web template
# web_include_css = "/assets/jack_test/css/jack_test.css"
# web_include_js = "/assets/jack_test/js/jack_test.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "jack_test/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "jack_test/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "jack_test.utils.jinja_methods",
# 	"filters": "jack_test.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "jack_test.install.before_install"
# after_install = "jack_test.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "jack_test.uninstall.before_uninstall"
# after_uninstall = "jack_test.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "jack_test.utils.before_app_install"
# after_app_install = "jack_test.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "jack_test.utils.before_app_uninstall"
# after_app_uninstall = "jack_test.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "jack_test.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "jack_test.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["jack_test.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"jack_test.tasks.all"
# 	],
# 	"daily": [
# 		"jack_test.tasks.daily"
# 	],
# 	"hourly": [
# 		"jack_test.tasks.hourly"
# 	],
# 	"weekly": [
# 		"jack_test.tasks.weekly"
# 	],
# 	"monthly": [
# 		"jack_test.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "jack_test.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "jack_test.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "jack_test.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "jack_test.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["jack_test.utils.before_request"]
# after_request = ["jack_test.utils.after_request"]

# Job Events
# ----------
# before_job = ["jack_test.utils.before_job"]
# after_job = ["jack_test.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"jack_test.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

