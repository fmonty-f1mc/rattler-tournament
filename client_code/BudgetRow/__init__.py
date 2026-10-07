from ._anvil_designer import BudgetRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class BudgetRow(BudgetRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.category_rows.items = self.item["categories"]
    self.paid_box.text = self._display_amount(self.item["entry"]["amount_paid"])
    self.share_total.text = "Estimated share: ${:,.2f}".format(self.item["estimated_share"])

  @staticmethod
  def _display_amount(value):
    return "" if value is None else str(value)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    categories = [
      getattr(row, "item")["category"]
      for row in self.category_rows.get_components()
      if getattr(row, "category_share_check").checked
    ]
    self.parent.raise_event(
      "x-save-entry-budget",
      entry=self.item["entry"],
      categories=categories,
      amount_paid=self.paid_box.text,
    )
