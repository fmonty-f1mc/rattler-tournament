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
    self.amount_owed_label.text = "Amount owed: ${:,.2f}".format(self.item["estimated_share"])
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
