import frappe
from frappe.utils import flt

_original_execute = None
_original_get_buying_amount = None


def set_original_execute(func):
    global _original_execute
    _original_execute = func


def set_original_get_buying_amount(func):
    global _original_get_buying_amount
    _original_get_buying_amount = func



def execute(filters=None):
    if not _original_execute:
        frappe.throw("Original Gross Profit execute method not initialized")

    filters = frappe._dict(filters or {})

    result = _original_execute(filters)

    if not result or len(result) < 2:
        return result

    columns, data = result[0], result[1]

    columns, data = add_extra_costs_to_item_report(
        columns, data, filters
    )

    return columns, data

def get_company_expense_account(company):
    if not company:
        return None

    return frappe.db.get_value(
        "Company",
        company,
        "default_expense_account"
    )


def get_document_gl_amount(company, account, voucher_type, voucher_no):
    """
    Get total GL amount for one document.
    Returns None when no matching GL entry exists.
    """

    if not all([company, account, voucher_type, voucher_no]):
        return None

    result = frappe.db.sql(
        """
        SELECT
            COUNT(name) AS entry_count,
            SUM(debit - credit) AS amount
        FROM `tabGL Entry`
        WHERE
            company = %s
            AND account = %s
            AND voucher_type = %s
            AND voucher_no = %s
            AND is_cancelled = 0
        """,
        (company, account, voucher_type, voucher_no),
        as_dict=True
    )

    if result and result[0].entry_count:
        return flt(result[0].amount)

    return None


def get_item_weight(item):
    """
    Use quantity x incoming rate as allocation weight.
    """

    qty = abs(flt(item.get("qty")))
    rate = abs(flt(item.get("incoming_rate")))

    return qty * rate


def allocate_document_gl(
    company,
    account,
    voucher_type,
    voucher_no,
    child_doctype,
    child_name
):
    """
    Allocate document-level GL amount to one child item.
    Allocation is based on qty x incoming_rate.
    """

    if not all([
        company,
        account,
        voucher_type,
        voucher_no,
        child_doctype,
        child_name
    ]):
        return None

    total_gl = get_document_gl_amount(
        company,
        account,
        voucher_type,
        voucher_no
    )

    if total_gl is None:
        return None

    items = frappe.get_all(
        child_doctype,
        filters={"parent": voucher_no},
        fields=["name", "qty", "incoming_rate"]
    )

    if not items:
        return None

    target = next(
        (item for item in items if item.name == child_name),
        None
    )

    if not target:
        return None

    weights = {
        item.name: get_item_weight(item)
        for item in items
    }

    total_weight = sum(weights.values())

    # Fallback 1: allocate by quantity if all incoming rates are zero.
    if total_weight <= 0:
        weights = {
            item.name: abs(flt(item.qty))
            for item in items
        }
        total_weight = sum(weights.values())

    # Fallback 2: equal allocation if quantities are also zero.
    if total_weight <= 0:
        weights = {
            item.name: 1.0
            for item in items
        }
        total_weight = len(items)

    target_weight = weights.get(target.name, 0)

    if total_weight <= 0:
        return None

    return flt(total_gl * target_weight / total_weight, 6)


def get_uninvoiced_dn_costs(company, account, from_date, to_date):
    """
    Get submitted Delivery Note costs that have no submitted
    Sales Invoice linked to the same Sales Order Item.
    """
    rows = frappe.db.sql("""
        SELECT
            dni.name,
            dni.parent,
            dni.item_code
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn
            ON dn.name = dni.parent
        WHERE
            dn.company = %s
            AND dn.docstatus = 1
            AND dn.posting_date BETWEEN %s AND %s
            AND IFNULL(dni.so_detail, '') != ''
            AND EXISTS (
                SELECT 1
                FROM `tabGL Entry` gle
                WHERE
                    gle.company = %s
                    AND gle.account = %s
                    AND gle.voucher_type = 'Delivery Note'
                    AND gle.voucher_no = dni.parent
                    AND gle.is_cancelled = 0
                    AND gle.debit > gle.credit
            )
            AND NOT EXISTS (
                SELECT 1
                FROM `tabSales Invoice Item` sii
                INNER JOIN `tabSales Invoice` si
                    ON si.name = sii.parent
                WHERE
                    sii.so_detail = dni.so_detail
                    AND si.docstatus = 1
            )
        ORDER BY dni.parent, dni.idx
    """, (company, from_date, to_date, company, account), as_dict=True)

    costs = {}

    for row in rows:
        amount = allocate_document_gl(
            company=company,
            account=account,
            voucher_type="Delivery Note",
            voucher_no=row.parent,
            child_doctype="Delivery Note Item",
            child_name=row.name
        )

        if amount is not None:
            costs[row.item_code] = (
                costs.get(row.item_code, 0) + flt(amount)
            )

    return costs



def get_purchase_invoice_costs_by_item(company, account, from_date, to_date):
    """
    Get Purchase Invoice costs by Item Code.

    Include only Purchase Invoice Item rows where:
    pii.expense_account == Company.default_expense_account

    GL amount is taken from the same company and expense account.
    Item.default_expense_account is NOT used.
    """

    if not all([company, account, from_date, to_date]):
        return {}

    items = frappe.db.sql("""
        SELECT
            pii.name,
            pii.parent,
            pii.item_code,
            pii.qty,
            pii.base_net_amount,
            pii.base_amount
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        WHERE
            pi.company = %s
            AND pi.docstatus = 1
            AND pi.posting_date BETWEEN %s AND %s
            AND pii.expense_account = %s
    """, (company, from_date, to_date, account), as_dict=True)

    if not items:
        return {}

    vouchers = list(set(item.parent for item in items))
    result = {}

    for voucher_no in vouchers:
        voucher_items = [
            item for item in items
            if item.parent == voucher_no
        ]

        # GL of this Purchase Invoice and this exact account only.
        gl_amount = frappe.db.sql("""
            SELECT COALESCE(SUM(debit - credit), 0)
            FROM `tabGL Entry`
            WHERE
                company = %s
                AND account = %s
                AND voucher_type = 'Purchase Invoice'
                AND voucher_no = %s
                AND is_cancelled = 0
        """, (company, account, voucher_no))[0][0]

        gl_amount = flt(gl_amount)

        if not gl_amount:
            continue

        # Allocate only among PI Item rows matching the account.
        weights = {}

        for item in voucher_items:
            weight = abs(flt(item.base_net_amount))

            if not weight:
                weight = abs(flt(item.base_amount))

            weights[item.name] = weight

        total_weight = sum(weights.values())

        if total_weight <= 0:
            weights = {
                item.name: abs(flt(item.qty))
                for item in voucher_items
            }
            total_weight = sum(weights.values())

        if total_weight <= 0:
            weights = {
                item.name: 1.0
                for item in voucher_items
            }
            total_weight = len(voucher_items)

        if total_weight <= 0:
            continue

        for item in voucher_items:
            if not item.item_code:
                continue

            allocated = (
                gl_amount * weights[item.name] / total_weight
            )

            result[item.item_code] = (
                result.get(item.item_code, 0) + allocated
            )

    return {
        item_code: flt(amount, 6)
        for item_code, amount in result.items()
    }


def add_extra_costs_to_item_report(columns, data, filters):
    """
    Modify Item Code grouped Gross Profit report:
    1. Add uninvoiced Delivery Note costs to their products.
    2. Add Purchase Invoice costs when expense_account matches
       Company's default_expense_account.
    3. Recalculate item gross profit and total row.
    """

    if filters.get("group_by") != "Item Code":
        return columns, data

    company = filters.get("company")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    account = get_company_expense_account(company)

    if not account:
        return columns, data

    # Column positions for Item Code report:
    # 0 item_code
    # 1 item_name
    # 2 brand
    # 3 description
    # 4 qty
    # 5 base_rate
    # 6 buying_rate
    # 7 base_amount
    # 8 buying_amount
    # 9 gross_profit
    # 10 gross_profit_percent
    # 11 currency

    item_index = 0
    selling_index = 7
    buying_index = 8
    profit_index = 9
    percent_index = 10

    # Find total row.
    total_row = next(
        (
            row for row in data
            if isinstance(row, (list, tuple))
            and row
            and row[0] == "Total"
        ),
        None
    )

    if total_row is None:
        return columns, data

    # Ensure rows can be modified.
    for i, row in enumerate(data):
        if isinstance(row, tuple):
            data[i] = list(row)

    # Find total row again after converting tuples.
    total_row = next(
        (
            row for row in data
            if isinstance(row, list)
            and row
            and row[0] == "Total"
        ),
        None
    )

    if total_row is None:
        return columns, data

    def add_cost_to_item(item_code, amount):
        amount = flt(amount)

        if not item_code or not amount:
            return

        target = next(
            (
                row for row in data
                if isinstance(row, list)
                and row
                and row[item_index] == item_code
                and row[0] != "Total"
            ),
            None
        )

        if target:
            target[buying_index] = flt(
                flt(target[buying_index]) + amount, 3
            )
        else:
            item_name = frappe.db.get_value(
                "Item", item_code, "item_name"
            ) or item_code

            new_row = [
                item_code,
                item_name,
                "",
                "",
                0,
                0,
                0,
                0,
                flt(amount, 3),
                flt(-amount, 3),
                0,
                filters.get("currency")
            ]

            data.insert(data.index(total_row), new_row)

    # 1. Add uninvoiced Delivery Note costs.
    dn_costs = get_uninvoiced_dn_costs(
        company, account, from_date, to_date
    )

    for item_code, amount in dn_costs.items():
        add_cost_to_item(item_code, amount)

    # 2. Add Purchase Invoice costs dynamically.
    # Only PI Item rows whose expense_account matches
    # Company's default_expense_account are included.
    pi_costs = get_purchase_invoice_costs_by_item(
        company, account, from_date, to_date
    )

    for item_code, amount in pi_costs.items():
        add_cost_to_item(item_code, amount)

    # 3. Recalculate Gross Profit for every detail row.
    detail_rows = [
        row for row in data
        if isinstance(row, list)
        and row
        and row[0] != "Total"
    ]

    for row in detail_rows:
        selling = flt(row[selling_index])
        buying = flt(row[buying_index])
        profit = selling - buying

        row[profit_index] = flt(profit, 3)
        row[percent_index] = (
            flt(profit / abs(selling) * 100, 3)
            if selling else 0
        )

    # 4. Recalculate Total from all detail rows.
    total_selling = sum(
        flt(row[selling_index]) for row in detail_rows
    )
    total_buying = sum(
        flt(row[buying_index]) for row in detail_rows
    )
    total_profit = total_selling - total_buying

    total_row[selling_index] = flt(total_selling, 3)
    total_row[buying_index] = flt(total_buying, 3)
    total_row[profit_index] = flt(total_profit, 3)
    total_row[percent_index] = (
        flt(total_profit / abs(total_selling) * 100, 3)
        if total_selling else 0
    )

    return columns, data



def get_dn_buying_amount_by_so_detail(company, account, so_detail, item_code, preferred_dn=None):
    if not all([company, account, so_detail, item_code]):
        return None

    rows = frappe.db.sql("""
        SELECT
            dni.name,
            dni.parent
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn
            ON dn.name = dni.parent
        WHERE
            dn.company = %s
            AND dn.docstatus = 1
            AND dni.so_detail = %s
            AND dni.item_code = %s
        ORDER BY dn.posting_date, dni.idx
    """, (company, so_detail, item_code), as_dict=True)

    if preferred_dn:
        preferred = [r for r in rows if r.parent == preferred_dn]
        if len(preferred) == 1:
            rows = preferred

    # ถ้าพบมากกว่าหนึ่ง DN และระบุไม่ได้แน่ชัด ห้ามเลือกเอง
    if len(rows) != 1:
        return None

    dn_item = rows[0]

    return allocate_document_gl(
        company=company,
        account=account,
        voucher_type="Delivery Note",
        voucher_no=dn_item.parent,
        child_doctype="Delivery Note Item",
        child_name=dn_item.name
    )

def get_buying_amount(self, row, item_code):
    """
    Use actual GL from Company's Default Expense Account.
    Support Delivery Note lookup through Sales Order Item.
    """

    company = self.filters.company
    account = get_company_expense_account(company)

    if not account:
        return _original_get_buying_amount(self, row, item_code)

    # Preserve standard handling for drop shipments.
    if row.get("delivered_by_supplier"):
        return _original_get_buying_amount(self, row, item_code)

    # Preserve standard handling for non-stock items.
    if item_code in self.non_stock_items:
        return _original_get_buying_amount(self, row, item_code)

    # Case 1: Direct link to Delivery Note Item.
    if row.get("dn_detail") and row.get("delivery_note"):
        amount = allocate_document_gl(
            company=company,
            account=account,
            voucher_type="Delivery Note",
            voucher_no=row.get("delivery_note"),
            child_doctype="Delivery Note Item",
            child_name=row.get("dn_detail")
        )

        if amount is not None:
            return amount

    # Case 2: Find Delivery Note through Sales Order Item.
    if row.get("so_detail"):
        amount = get_dn_buying_amount_by_so_detail(
            company=company,
            account=account,
            so_detail=row.get("so_detail"),
            item_code=item_code,
            preferred_dn=row.get("delivery_note")
        )

        if amount is not None:
            return amount

    # Case 3: Sales Invoice updates stock directly.
    if row.get("update_stock"):
        invoice_no = row.get("invoice") or row.get("parent")

        amount = allocate_document_gl(
            company=company,
            account=account,
            voucher_type="Sales Invoice",
            voucher_no=invoice_no,
            child_doctype="Sales Invoice Item",
            child_name=row.get("item_row")
        )

        if amount is not None:
            return amount

    # No matching GL cost.
    return 0.0