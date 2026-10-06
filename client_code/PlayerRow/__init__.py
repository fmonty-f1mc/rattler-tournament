from ._anvil_designer import PlayerRowTemplate
from anvil import *


class PlayerRow(PlayerRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.division_dropdown.items = ["Division 1", "Division 2", "Division 3"]
    self.division_dropdown.selected_value = self.item["division"]
    self.handicap_box.text = str(self.item["handicap"])
    self.active_label.text = "Active roster" if self.item["active"] else "Inactive · retained for history"
    self.toggle_button.text = "Set inactive" if self.item["active"] else "Reactivate"

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-player",
      golfer=self.item,
      division=self.division_dropdown.selected_value,
      handicap=self.handicap_box.text,
    )

  @handle("toggle_button", "click")
  def toggle_button_click(self, **event_args):
    self.parent.raise_event(
      "x-toggle-player",
      golfer=self.item,
      active=not self.item["active"],
    )
