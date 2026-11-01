from ._anvil_designer import PublicBudgetRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class PublicBudgetRow(PublicBudgetRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.estimated_share_label.text = self._money(self.item["estimated_share"])
    self.paid_label.text = self._money(self.item["paid"])
    self.balance_label.text = self._money(self.item["balance"])

  @staticmethod
  def _money(value):
    return "${:,.2f}".format(value or 0)
