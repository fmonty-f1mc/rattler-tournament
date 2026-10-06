from ._anvil_designer import BudgetRowTemplate
from anvil import *


class BudgetRow(BudgetRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.accommodation_check.checked = self.item["shares_accommodation"]
    self.golf_check.checked = self.item["shares_golf"]
    self.travel_check.checked = self.item["shares_travel"]
    self.other_check.checked = self.item["shares_other"]
    self.accommodation_check.text = self._share_label(
      "Accommodation", self.item["accommodation_share"], self.item["accommodation_count"]
    )
    self.golf_check.text = self._share_label("Golf", self.item["golf_share"], self.item["golf_count"])
    self.travel_check.text = self._share_label("Travel", self.item["travel_share"], self.item["travel_count"])
    self.other_check.text = self._share_label("Other", self.item["other_share"], self.item["other_count"])
    self.paid_box.text = self._display_amount(self.item["entry"]["amount_paid"])
    self.share_total.text = "Estimated share: ${:,.2f}".format(self.item["estimated_share"])

  @staticmethod
  def _display_amount(value):
    return "" if value is None else str(value)

  @staticmethod
  def _share_label(category, value, count):
    if count:
      return f"{category} · ${value:,.2f}/player ({count} sharing)"
    return f"{category} · ${value:,.2f} if you're first"

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-entry-budget",
      entry=self.item["entry"],
      shares_accommodation=self.accommodation_check.checked,
      shares_golf=self.golf_check.checked,
      shares_travel=self.travel_check.checked,
      shares_other=self.other_check.checked,
      amount_paid=self.paid_box.text,
    )
