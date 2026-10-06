from ._anvil_designer import BudgetRowTemplate
from anvil import *


class BudgetRow(BudgetRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.accommodation_check.checked = bool(self.item["accommodation"])
    self.lodging_box.text = self._display_amount(self.item["lodging_cost"])
    self.golf_box.text = self._display_amount(self.item["golf_cost"])
    self.travel_box.text = self._display_amount(self.item["travel_cost"])
    self.other_box.text = self._display_amount(self.item["other_cost"])
    self.paid_box.text = self._display_amount(self.item["amount_paid"])

  @staticmethod
  def _display_amount(value):
    return "" if value is None else str(value)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-entry-budget",
      entry=self.item,
      accommodation=self.accommodation_check.checked,
      lodging=self.lodging_box.text,
      golf=self.golf_box.text,
      travel=self.travel_box.text,
      other=self.other_box.text,
      paid=self.paid_box.text,
    )
