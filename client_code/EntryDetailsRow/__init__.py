from ._anvil_designer import EntryDetailsRowTemplate
from anvil import *


class EntryDetailsRow(EntryDetailsRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    entry = self.item["entry"]
    self.division_dropdown.items = self.item["division_options"]
    self.division_dropdown.selected_value = entry["division"] or None
    handicap = entry["handicap"]
    self.handicap_box.text = "" if handicap is None else str(handicap)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-entry-details",
      entry=self.item["entry"],
      division=self.division_dropdown.selected_value,
      handicap=self.handicap_box.text,
    )
