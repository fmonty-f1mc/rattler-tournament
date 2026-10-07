from ._anvil_designer import BudgetRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class BudgetRow(BudgetRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.payment_selection_checkbox.checked = self.item["payment_selected"]
    self.paid_box.text = self._display_amount(
      self.item.get("draft_paid", self.item["entry"]["amount_paid"])
    )
    self.paid_box.enabled = False
    saved_paid = self.item["entry"]["amount_paid"] or 0
    paid_amount = self.item.get("draft_paid", saved_paid)
    try:
      paid_amount = float(paid_amount)
    except (TypeError, ValueError):
      paid_amount = saved_paid
    amount_owed = self.item["estimated_share"] - paid_amount
    self.amount_owed_label.text = "Amount owed: ${:,.2f}".format(amount_owed)
    self.amount_owed_label.role = (
      "budget-settled" if amount_owed <= 0 else "budget-owed"
    )
    expense_details = [
      category for category in self.item["categories"] if category["selected"]
    ]
    self.expense_rows.items = expense_details
    self.no_expenses_label.visible = not expense_details

  @staticmethod
  def _display_amount(value):
    return "0" if value is None else str(value)

  @handle("payment_selection_checkbox", "change")
  def payment_selection_checkbox_change(self, **event_args):
    self.item["payment_selected"] = self.payment_selection_checkbox.checked
    self.parent.raise_event("x-budget-payment-selection-changed")
