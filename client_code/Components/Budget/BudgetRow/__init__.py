from ._anvil_designer import BudgetRowTemplate
from anvil import *


class BudgetRow(BudgetRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    saved_paid = self.item["entry"]["amount_paid"] or 0
    amount_owed = round(self.item["estimated_share"] - saved_paid, 2)
    self.amount_owed_label.text = "${:,.2f}".format(amount_owed)
    self.amount_owed_label.role = (
      "budget-settled" if amount_owed <= 0 else "budget-owed"
    )
    self.payment_state_label.text = (
      "Outstanding" if amount_owed > 0 else "Credit" if amount_owed < 0 else "Settled"
    )
    self.payment_state_label.role = (
      "payment-state-due" if amount_owed > 0 else "payment-state-settled"
    )
    expense_details = [
      category for category in self.item["categories"] if category["selected"]
    ]
    self.expense_rows.items = expense_details
    self.no_expenses_label.visible = not expense_details
    paid_count = sum(1 for category in expense_details if category["paid"])
    self.category_payment_count_label.text = (
      f"{paid_count} of {len(expense_details)} categories paid"
      if expense_details else "No categories assigned"
    )
    self._update_expense_disclosure()
    self._update_selection_style()

  def _update_expense_disclosure(self):
    expanded = self.item.get("_expanded", False)
    self.expense_details_panel.visible = expanded
    self.toggle_expenses_button.text = (
      "Hide categories ↑" if expanded else "Expense categories ↓"
    )

  def _update_selection_style(self):
    self.role = (
      "payment-participant-card-selected"
      if self.item["payment_selected"] else "payment-participant-card"
    )

  @handle("toggle_expenses_button", "click")
  def toggle_expenses_button_click(self, **event_args):
    self.item["_expanded"] = not self.item.get("_expanded", False)
    self._update_expense_disclosure()

  @handle("expense_rows", "x-budget-category-paid-changed")
  def expense_rows_category_paid_changed(self, entry, category, paid, **event_args):
    self.parent.raise_event(
      "x-budget-category-paid-changed", entry=entry, category=category, paid=paid,
    )

  @handle("payment_selection_checkbox", "change")
  def payment_selection_checkbox_change(self, **event_args):
    self.item["payment_selected"] = self.payment_selection_checkbox.checked
    self._update_selection_style()
    self.parent.raise_event("x-budget-payment-selection-changed")
