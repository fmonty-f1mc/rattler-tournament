from ._anvil_designer import PlayerRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class PlayerRow(PlayerRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.email_box.text = self.item["email"] or ""
    self.phone_box.text = self.item["phone"] or ""
    self.city_box.text = self.item["city"] or ""
    self.state_box.text = self.item["state"] or ""
    self.active_label.text = "Active roster" if self.item["active"] else "Inactive · retained for history"
    self.toggle_button.text = "Set inactive" if self.item["active"] else "Reactivate"

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-player",
      golfer=self.item,
      email=self.email_box.text,
      phone=self.phone_box.text,
      city=self.city_box.text,
      state=self.state_box.text,
    )

  @handle("toggle_button", "click")
  def toggle_button_click(self, **event_args):
    self.parent.raise_event(
      "x-toggle-player",
      golfer=self.item,
      active=not self.item["active"],
    )

  @handle("delete_button", "click")
  def delete_button_click(self, **event_args):
    self.parent.raise_event("x-delete-player", golfer=self.item)
