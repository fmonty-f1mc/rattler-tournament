from ._anvil_designer import ExpenseDetailRowTemplate
from anvil import *


class ExpenseDetailRow(ExpenseDetailRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.expense_share_label.text = "${:,.2f} per person".format(self.item["share"])
    count = self.item["count"]
    self.sharing_count_label.text = f"{count} participant" + ("s" if count != 1 else "")
