
import frappe


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = [
        {
            "fieldname": "serial_no",
            "label": "Serial No",
            "fieldtype": "Link",
            "options": "Serial No",
            "width": 150
        },
        {
            "fieldname": "item_code",
            "label": "Item Code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
         {
            "fieldname": "actual_cost",
            "label": "Actual Cost/Unit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "cost_date",
            "label": "Cost Date",
            "fieldtype": "Datetime",
            "width": 145
        },
        {
            "fieldname": "current_status",
            "label": "Current Status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "current_warehouse",
            "label": "Current Warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        },
        {
            "fieldname": "target_shelf",
            "label": "Target Shelf",
            "fieldtype": "Data",
            "width": 120
        },        
        {
            "fieldname": "latest_voucher",
            "label": "Latest Voucher",
            "fieldtype": "Dynamic Link",
            "options": "latest_voucher_type",
            "width": 170
        },
        {
            "fieldname": "latest_voucher_type",
            "label": "Latest Voucher Type",
            "fieldtype": "Data",
            "hidden": 1
        },        
        {
            "fieldname": "previous_serials",
            "label": "Previous Serial (A)",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "previous_cost",
            "label": "Previous Cost",
            "fieldtype": "Data",
            "width": 130
        },
        {
            "fieldname": "repack_docs",
            "label": "Repack Document",
            "fieldtype": "Link",
            "options": "Stock Entry",
            "width": 160
        },
        {
            "fieldname": "next_serials",
            "label": "Next Serial (B)",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "origin_voucher",
            "label": "Origin Voucher",
            "fieldtype": "Dynamic Link",
            "options": "origin_voucher_type",
            "width": 160
        },
        {
            "fieldname": "origin_voucher_type",
            "label": "Origin Voucher Type",
            "fieldtype": "Data",
            "hidden": 1
        },
        {
            "fieldname": "origin_warehouse",
            "label": "Origin Warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        },
        {
            "fieldname": "customer",
            "label": "Customer",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "warranty_start_date",
            "label": "Warranty Start Date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "warranty_period",
            "label": "Warranty Period (Days)",
            "fieldtype": "Int",
            "width": 130
        },
        {
            "fieldname": "warranty_expiry_date",
            "label": "Warranty Expiry Date",
            "fieldtype": "Date",
            "width": 130
        },
        {
            "fieldname": "amc_expiry_date",
            "label": "AMC Expiry Date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "maintenance_status",
            "label": "Maintenance Status",
            "fieldtype": "Data",
            "width": 140
        }        
    ]


    # Build conditions only for filters that have values.
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append(
            "DATE(origin.posting_datetime) >= %(from_date)s"
        )
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions.append(
            "DATE(origin.posting_datetime) <= %(to_date)s"
        )
        values["to_date"] = filters.to_date

    if filters.get("item_code"):
        conditions.append(
            "sn.item_code = %(item_code)s"
        )
        values["item_code"] = filters.item_code

    serial_nos = filters.get("serial_no") or []

    if isinstance(serial_nos, str):
        try:
            serial_nos = frappe.parse_json(serial_nos)
        except (ValueError, TypeError):
            serial_nos = [serial_nos]

    if serial_nos:
        conditions.append("sn.name IN %(serial_nos)s")
        values["serial_nos"] = tuple(serial_nos)
        
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = """
        SELECT
            sn.name AS serial_no,
            sn.item_code AS item_code,
            origin.incoming_rate AS actual_cost,
            origin.posting_datetime AS cost_date,
            origin.voucher_no AS origin_voucher,
            origin.voucher_type AS origin_voucher_type,
            origin.warehouse AS origin_warehouse,

            prev.previous_serials AS previous_serials,
            prev.previous_cost AS previous_cost,
            prev.repack_docs AS repack_docs,

            nxt.next_serials AS next_serials,

            sn.status AS current_status,
            sn.warehouse AS current_warehouse,
            sn.customer AS customer,
            
            DATE(warranty_start.posting_datetime) AS warranty_start_date,
            sn.warranty_period AS warranty_period,
            sn.warranty_expiry_date AS warranty_expiry_date,
            sn.amc_expiry_date AS amc_expiry_date,
            sn.maintenance_status AS maintenance_status,            
            
            CASE
                WHEN latest_entry.voucher_type = 'Stock Entry'
                    THEN latest_detail.to_shelf
                ELSE NULL
            END AS target_shelf,
            latest_entry.voucher_no AS latest_voucher,
            latest_entry.voucher_type AS latest_voucher_type        
        FROM `tabSerial No` sn

        LEFT JOIN `tabSerial and Batch Entry` origin
            ON origin.name = (
                SELECT e.name
                FROM `tabSerial and Batch Entry` e
                WHERE e.serial_no = sn.name
                  AND e.item_code = sn.item_code
                  AND e.type_of_transaction = 'Inward'
                  AND e.qty > 0
                  AND e.is_cancelled = 0
                  AND e.docstatus = 1
                ORDER BY e.posting_datetime ASC, e.creation ASC
                LIMIT 1
            )

          LEFT JOIN (
            SELECT
                p.fg_serial_no,

                GROUP_CONCAT(
                    p.serial_no
                    ORDER BY p.serial_no
                    SEPARATOR ', '
                ) AS previous_serials,

                GROUP_CONCAT(
                    IFNULL(FORMAT(p.incoming_rate, 2), 'N/A')
                    ORDER BY p.serial_no
                    SEPARATOR ', '
                ) AS previous_cost,

                GROUP_CONCAT(
                    DISTINCT p.voucher_no
                    ORDER BY p.voucher_no
                    SEPARATOR ', '
                ) AS repack_docs

            FROM (
                SELECT DISTINCT
                    e.fg_serial_no,
                    old_sn.serial_no,
                    e.voucher_no,

                    (
                        SELECT old_entry.incoming_rate
                        FROM `tabSerial and Batch Entry` old_entry
                        WHERE old_entry.serial_no = old_sn.name
                          AND old_entry.item_code = old_sn.item_code
                          AND old_entry.type_of_transaction = 'Inward'
                          AND old_entry.qty > 0
                          AND old_entry.is_cancelled = 0
                          AND old_entry.docstatus = 1
                        ORDER BY
                            old_entry.posting_datetime ASC,
                            old_entry.creation ASC
                        LIMIT 1
                    ) AS incoming_rate

                FROM `tabSerial and Batch Entry` e

                INNER JOIN `tabSerial No` old_sn
                    ON old_sn.name = e.serial_no

                WHERE e.fg_serial_no IS NOT NULL
                  AND e.fg_serial_no != ''
                  AND e.is_cancelled = 0
                  AND e.docstatus = 1

            ) p

            GROUP BY p.fg_serial_no
        ) prev
            ON prev.fg_serial_no = sn.name

        LEFT JOIN (
            SELECT
                e.serial_no,

                GROUP_CONCAT(
                    DISTINCT new_sn.serial_no
                    ORDER BY new_sn.serial_no
                    SEPARATOR ', '
                ) AS next_serials

            FROM `tabSerial and Batch Entry` e

            INNER JOIN `tabSerial No` new_sn
                ON new_sn.name = e.fg_serial_no

            WHERE e.fg_serial_no IS NOT NULL
              AND e.fg_serial_no != ''
              AND e.is_cancelled = 0
              AND e.docstatus = 1

            GROUP BY e.serial_no
        ) nxt
            ON nxt.serial_no = sn.name

    LEFT JOIN `tabSerial and Batch Entry` latest_entry
        ON latest_entry.serial_no = sn.name
        AND latest_entry.is_cancelled = 0
        AND latest_entry.docstatus = 1
        AND latest_entry.name = (
            SELECT se2.name
            FROM `tabSerial and Batch Entry` se2
            WHERE se2.serial_no = sn.name
            AND se2.is_cancelled = 0
            AND se2.docstatus = 1
            ORDER BY
                se2.posting_datetime DESC,
                se2.creation DESC,
                se2.name DESC
            LIMIT 1
        )

    LEFT JOIN `tabStock Entry Detail` latest_detail
        ON latest_detail.name = latest_entry.voucher_detail_no

    LEFT JOIN `tabDelivery Note Item` latest_dn_detail
        ON latest_dn_detail.name = latest_entry.voucher_detail_no
           
    LEFT JOIN `tabSerial and Batch Entry` warranty_start
        ON warranty_start.name = (
            SELECT ws.name
            FROM `tabSerial and Batch Entry` ws
            WHERE ws.serial_no = sn.name
              AND ws.is_outward = 1
              AND ws.voucher_type IN ('Delivery Note', 'Sales Invoice')
              AND ws.is_cancelled = 0
              AND ws.docstatus = 1
            ORDER BY
                ws.posting_datetime ASC,
                ws.creation ASC,
                ws.name ASC
            LIMIT 1
        )                  

        {where_clause}

        ORDER BY
            origin.posting_datetime DESC,
            sn.serial_no ASC
    """.format(where_clause=where_clause)

    data = frappe.db.sql(
        query,
        values=values,
        as_dict=True
    )

    return columns, data
