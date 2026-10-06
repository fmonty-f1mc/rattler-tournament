from ._anvil_designer import EntryDetailsRowTemplate
from anvil import *


class EntryDetailsRow(EntryDetailsRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.division_dropdown.items = self.item["division_options"]

  @handle("division_dropdown", "change")
  def division_dropdown_change(self, **event_args):
    self.item["division"] = self.division_dropdown.selected_value

  @handle("handicap_box", "change")
  def handicap_box_change(self, **event_args):
    self.item["handicap"] = self.handicap_box.text

  @handle("remove_button", "click")
  def remove_button_click(self, **event_args):
    self.parent.raise_event("x-remove-entry", entry=self.item["entry"])
