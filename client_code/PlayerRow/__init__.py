from ._anvil_designer import PlayerRowTemplate
from anvil import *
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
      self.active_label,
    ):
      component.visible = not editing

    for component in (
      self.name_box,
      self.email_box,
      self.phone_box,
      self.city_box,
      self.state_box,
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
    self.name_button.text = f"{name}  {marker}"

  def _restore_item_values(self):
    self.name_box.text = self.item["name"] or ""
    self.email_box.text = self.item["email"] or ""
    self.phone_box.text = self.item["phone"] or ""
    self.city_box.text = self.item["city"] or ""
    self.state_box.text = self.item["state"] or ""
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
    )

  @handle("delete_button", "click")
  def delete_button_click(self, **event_args):
    self.parent.raise_event("x-delete-player", golfer=self.item)
