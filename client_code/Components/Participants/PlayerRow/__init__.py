from ._anvil_designer import PlayerRowTemplate
from anvil import *
import anvil.server
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class PlayerRow(PlayerRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.name_box.text = self.item["name"] or ""
    self.email_box.text = self.item["email"] or ""
    self.phone_box.text = self.item["phone"] or ""
    self.city_box.text = self.item["city"] or ""
    self.state_box.text = self.item["state"] or ""
    self.handicap_box.text = "" if self.item["handicap"] is None else str(self.item["handicap"])
    self.official_checkbox.checked = bool(self.item["handicap_official"])
    self.active_picker.items = [("Active", True), ("Inactive", False)]
    self._load_active_state()
    self._set_editing(False)
    self._set_expanded(False)

  def _load_active_state(self):
    self.active_label.text = "Active" if self.item["active"] else "Inactive"
    self.active_picker.selected_value = bool(self.item["active"])

  def _set_editing(self, editing):
    self._editing = editing
    if editing:
      self._set_expanded(True)

    for component in (
      self.name_label,
      self.email_label,
      self.phone_label,
      self.city_label,
      self.state_label,
      self.handicap_label,
      self.active_label,
    ):
      component.visible = not editing

    for component in (
      self.name_box,
      self.email_box,
      self.phone_box,
      self.city_box,
      self.state_box,
      self.handicap_box,
      self.official_checkbox,
      self.active_picker,
      self.save_button,
      self.cancel_button,
    ):
      component.visible = editing

    self.edit_button.visible = not editing

  def _set_expanded(self, expanded):
    self._expanded = expanded
    self.details_panel.visible = expanded
    name = self.item["name"] or "Unnamed player"
    marker = "▾" if expanded else "▸"
    self.name_button.text = f"{marker}  {name}"
    if expanded:
      self._load_history()

  def _load_history(self):
    # Fetch only when opened, and refresh on reopening after awards/caps change.
    self.name_button.enabled = False
    try:
      result = anvil.server.call("get_participant_history", self.item)
      if not result["ok"]:
        self.history_table.visible = False
        self.history_status.text = result["message"]
        self.history_status.visible = True
        return
      years = result["years"]
      self.history_rows.items = years
      self.history_table.visible = bool(years)
      self.history_status.text = "No tournament history recorded yet."
      self.history_status.visible = not years
    finally:
      self.name_button.enabled = True

  def _restore_item_values(self):
    self.name_box.text = self.item["name"] or ""
    self.email_box.text = self.item["email"] or ""
    self.phone_box.text = self.item["phone"] or ""
    self.city_box.text = self.item["city"] or ""
    self.state_box.text = self.item["state"] or ""
    self.handicap_box.text = "" if self.item["handicap"] is None else str(self.item["handicap"])
    self.official_checkbox.checked = bool(self.item["handicap_official"])
    self._load_active_state()

  @handle("name_button", "click")
  def name_button_click(self, **event_args):
    if not self._editing:
      self._set_expanded(not self._expanded)

  @handle("edit_button", "click")
  def edit_button_click(self, **event_args):
    self._set_editing(True)

  @handle("cancel_button", "click")
  def cancel_button_click(self, **event_args):
    self._restore_item_values()
    self._set_editing(False)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-player",
      golfer=self.item,
      name=self.name_box.text,
      email=self.email_box.text,
      phone=self.phone_box.text,
      city=self.city_box.text,
      state=self.state_box.text,
      active=self.active_picker.selected_value,
      handicap=self.handicap_box.text,
      handicap_official=self.official_checkbox.checked,
    )

  @handle("delete_button", "click")
  def delete_button_click(self, **event_args):
    self.parent.raise_event("x-delete-player", golfer=self.item)
