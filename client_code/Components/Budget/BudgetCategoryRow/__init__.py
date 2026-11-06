from ._anvil_designer import BudgetCategoryRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class BudgetCategoryRow(BudgetCategoryRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.category_name_box.text = self.item["name"] or ""
    self.category_total_box.text = self._display_amount(self.item["amount"])
    self._per_person = self.item["per_person"]
    self._update_pricing_mode()

  def _update_pricing_mode(self):
    self.total_mode_button.role = "tournament-subtab" if self._per_person else "tournament-subtab-active"
    self.per_person_mode_button.role = "tournament-subtab-active" if self._per_person else "tournament-subtab"
    self.category_amount_label.text = "Per person $" if self._per_person else "Total $"

  @handle("total_mode_button", "click")
  def total_mode_button_click(self, **event_args):
    self._per_person = False
    self._update_pricing_mode()

  @handle("per_person_mode_button", "click")
  def per_person_mode_button_click(self, **event_args):
    self._per_person = True
    self._update_pricing_mode()

  @staticmethod
  def _display_amount(value):
    return "" if value is None else str(value)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-budget-category",
      category=self.item["category"],
      name=self.category_name_box.text,
      total=self.category_total_box.text,
      per_person=self._per_person,
    )

  @handle("delete_button", "click")
  def delete_button_click(self, **event_args):
    self.parent.raise_event(
      "x-delete-budget-category",
      category=self.item["category"],
    )
