from ._anvil_designer import AwardHistoryRowTemplate
from anvil import *


class AwardHistoryRow(AwardHistoryRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  @handle("remove_button", "click")
  def remove_button_click(self, **event_args):
    self.parent.raise_event("x-remove-award", record=self.item)
