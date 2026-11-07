from ._anvil_designer import EntryDetailsRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class EntryDetailsRow(EntryDetailsRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.division_dropdown.items = self.item["division_options"]

  def set_division(self, division):
    self.item["division"] = division
    self.division_dropdown.selected_value = division

  def set_handicap(self, handicap):
    self.item["handicap"] = handicap
    self.handicap_box.text = handicap

  @handle("division_dropdown", "change")
  def division_dropdown_change(self, **event_args):
    self.item["division"] = self.division_dropdown.selected_value
    self.parent.raise_event("x-field-details-changed")

  @handle("handicap_box", "change")
  def handicap_box_change(self, **event_args):
    self.item["handicap"] = self.handicap_box.text
    self.parent.raise_event("x-field-details-changed")

  @handle("select_player_checkbox", "change")
  def select_player_checkbox_change(self, **event_args):
    self.item["selected"] = self.select_player_checkbox.checked
    self.parent.raise_event("x-field-player-selection-changed")
