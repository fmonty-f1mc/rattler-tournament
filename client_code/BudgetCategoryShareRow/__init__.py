from ._anvil_designer import BudgetCategoryShareRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class BudgetCategoryShareRow(BudgetCategoryShareRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.category_share_check.checked = self.item["selected"]
    is_player = self.item["entry_is_player"]
    self.category_share_check.enabled = not (self.item["players_only"] and not is_player)
    self.category_share_check.text = self._share_label(
      self.item["name"],
      self.item["share"],
      self.item["count"],
    )

  @staticmethod
  def _share_label(category, value, count):
    if count:
      return f"{category} · ${value:,.2f}/participant ({count} sharing)"
    return f"{category} · ${value:,.2f} if you're first"
