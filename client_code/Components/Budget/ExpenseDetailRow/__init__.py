from ._anvil_designer import ExpenseDetailRowTemplate
from anvil import *


class ExpenseDetailRow(ExpenseDetailRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    count = self.item["count"]
    mode = "per person" if self.item["per_person"] else "sharing"
    self.sharing_count_label.text = f"{count} assigned · {mode}"

  @handle("paid_checkbox", "change")
  def paid_checkbox_change(self, **event_args):
    self.paid_checkbox.enabled = False
    try:
      self.parent.raise_event(
        "x-budget-category-paid-changed",
        entry=self.item["entry"],
        category=self.item["category"],
        paid=self.paid_checkbox.checked,
      )
    finally:
      self.paid_checkbox.enabled = True
      self.refresh_data_bindings()
