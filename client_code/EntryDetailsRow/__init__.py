from ._anvil_designer import EntryDetailsRowTemplate
from anvil import *


class EntryDetailsRow(EntryDetailsRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.division_dropdown.items = self.item["division_options"]
