import frappe


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def customer_query(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters=None,
    as_dict=False,
    reference_doctype=None,
    ignore_user_permissions=False,
    link_fieldname=None,
):
    """Search Customer using its normal fields and linked Address Tax ID."""

    doctype = "Customer"
    txt = (txt or "").strip()

    meta = frappe.get_meta(doctype)

    # Preserve Link field filters and the standard disabled-document behavior.
    if isinstance(filters, dict):
        filters = filters.copy()
        include_disabled = filters.pop("include_disabled", 0) == 1
    elif filters is None:
        filters = {}
        include_disabled = False
    else:
        filters = list(filters)
        include_disabled = False

    if not include_disabled and meta.get_field("disabled"):
        if isinstance(filters, dict):
            filters["disabled"] = ["!=", 1]
        else:
            filters.append([doctype, "disabled", "!=", 1])

    # Keep the same searchable Customer fields as Frappe's normal Link search.
    searchable_types = {
        "Autocomplete",
        "Data",
        "Text",
        "Small Text",
        "Long Text",
        "Link",
        "Select",
        "Read Only",
        "Text Editor",
    }

    search_fields = ["name"]

    if meta.title_field:
        search_fields.append(meta.title_field)

    if meta.search_fields:
        search_fields.extend(meta.get_search_fields())

    or_filters = []
    seen_fields = set()

    if txt:
        for fieldname in search_fields:
            fieldname = fieldname.strip()

            if fieldname in seen_fields:
                continue

            seen_fields.add(fieldname)

            field = meta.get_field(fieldname)
            if fieldname == "name" or (
                field and field.fieldtype in searchable_types
            ):
                or_filters.append(
                    [fieldname, "like", f"%{txt}%"]
                )

        # Search Tax ID on every Address linked to a Customer.
        tax_id_customers = frappe.db.sql(
            """
            SELECT DISTINCT dl.link_name
            FROM `tabDynamic Link` dl
            INNER JOIN `tabAddress` a
                ON a.name = dl.parent
            WHERE dl.parenttype = 'Address'
              AND dl.parentfield = 'links'
              AND dl.link_doctype = 'Customer'
              AND IFNULL(a.tax_id, '') != ''
              AND a.tax_id LIKE %s
            """,
            values=(f"%{txt}%",),
            pluck=True,
        )

        if tax_id_customers:
            or_filters.append(["name", "in", tax_id_customers])

    # Return the same fields normally shown by Customer Link search.
    fields = ["name"]

    if meta.title_field and meta.title_field not in fields:
        fields.append(meta.title_field)

    if searchfield and searchfield not in fields:
        if meta.get_field(searchfield):
            fields.append(searchfield)

    if meta.search_fields:
        for fieldname in meta.get_search_fields():
            fieldname = fieldname.strip()
            if fieldname not in fields and meta.get_field(fieldname):
                fields.append(fieldname)

    return frappe.get_list(
        doctype,
        filters=filters,
        fields=fields,
        or_filters=or_filters,
        limit_start=start,
        limit_page_length=page_len,
        order_by="idx desc, name asc",
        ignore_user_permissions=ignore_user_permissions,
        reference_doctype=reference_doctype,
        as_list=not as_dict,
        strict=False,
    )
