from ._anvil_designer import BudgetRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class BudgetRow(BudgetRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.paid_box.text = self._display_amount(
      self.item.get("draft_paid", self.item["entry"]["amount_paid"])
    )
    self.amount_owed_label.text = "Amount owed: ${:,.2f}".format(self.item["estimated_share"])

  @staticmethod
  def _display_amount(value):
    return "0" if value is None else str(value)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-entry-payment",
      entry=self.item["entry"],
      amount_paid=self.paid_box.text,
    )
