# Copyright (c) 2026, Tammanoon Deeying and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BookOrder(Document):
	pass

def compute_total(doc, method=None):
	total_amount = 0
	for item in doc.items:
		item.total_price = item.price * item.quantity
		total_amount += item.total_price
	doc.total_amount = total_amount


def confirm_date(doc, method=None):
	doc.confirm_date = frappe.utils.today()


def update_ordered_qty(doc, method=None):
	orders = frappe.db.get_all(
		"Book Order", filters={"docstatus": 1}, pluck="name"
	)
	book_qty = {}

	for order_name in orders:
		order = frappe.get_doc("Book Order", order_name)
		for item in order.items:
			book_qty[item.book] = book_qty.get(item.book, 0) + item.quantity

	for book, qty in book_qty.items():
		frappe.db.set_value("Book", book, "ordered_qty", qty)