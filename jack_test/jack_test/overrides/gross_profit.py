import importlib
import frappe


def install():
    target = importlib.import_module(
        "erpnext.accounts.report.gross_profit.gross_profit"
    )

    custom = importlib.import_module(
        "jack_test.jack_test.report.custom_gross_profit"
    )

    if getattr(target, "_jack_test_gp_patched", False):
        return

    # เก็บ Original Methods ของ ERPNext
    original_execute = target.execute
    original_get_buying_amount = (
        target.GrossProfitGenerator.get_buying_amount
    )

    custom.set_original_execute(original_execute)
    custom.set_original_get_buying_amount(
        original_get_buying_amount
    )

    # Patch Buying Amount
    target.GrossProfitGenerator.get_buying_amount = (
        custom.get_buying_amount
    )

    # Patch Execute
    target.execute = custom.execute

    target._jack_test_gp_patched = True

    frappe.logger("jack_test").info(
        "Gross Profit COGS Override installed successfully"
    )
