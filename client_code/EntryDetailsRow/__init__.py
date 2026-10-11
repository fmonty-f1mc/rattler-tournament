from ._anvil_designer import EntryDetailsRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class EntryDetailsRow(EntryDetailsRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self._is_editing = False
    self.division_dropdown.items = self.item["division_options"]
    self._update_entry_summary()
    self._set_editing(False)

  def _update_entry_summary(self):
    division = self.item.get("division") or "No division"
    handicap = self.item.get("handicap") or "Not set"
    self.entry_details_summary.text = (
      f"Division: {division} · Handicap: {handicap}"
    )

  def set_division(self, division):
    self.item["division"] = division
    self.division_dropdown.selected_value = division
    self._update_entry_summary()

  def set_handicap(self, handicap):
    self.item["handicap"] = handicap
    self.handicap_box.text = handicap
    self._update_entry_summary()

  def _set_editing(self, is_editing):
    self._is_editing = is_editing
    self.entry_edit_fields.visible = is_editing
    self.edit_button.text = "Done" if is_editing else "Edit"

  @handle("edit_button", "click")
  def edit_button_click(self, **event_args):
    self._set_editing(not self._is_editing)

  @handle("division_dropdown", "change")
  def division_dropdown_change(self, **event_args):
    self.item["division"] = self.division_dropdown.selected_value
    self._update_entry_summary()

  @handle("handicap_box", "change")
  def handicap_box_change(self, **event_args):
    self.item["handicap"] = self.handicap_box.text
    self._update_entry_summary()

  @handle("select_player_checkbox", "change")
  def select_player_checkbox_change(self, **event_args):
    self.item["selected"] = self.select_player_checkbox.checked
    self.parent.raise_event("x-field-player-selection-changed")
