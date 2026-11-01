from ._anvil_designer import BudgetCategoryRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class BudgetCategoryRow(BudgetCategoryRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.category_name_box.text = self.item["name"] or ""
    self.category_total_box.text = self._display_amount(self.item["total"])

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
    )

  @handle("delete_button", "click")
  def delete_button_click(self, **event_args):
    self.parent.raise_event(
      "x-delete-budget-category",
      category=self.item["category"],
    )
