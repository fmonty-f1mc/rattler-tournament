from ._anvil_designer import EntryPlayerChoiceTemplate
from anvil import handle
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class EntryPlayerChoice(EntryPlayerChoiceTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  @handle("player_checkbox", "change")
  def player_checkbox_change(self, **event_args):
    self.item["selected"] = self.player_checkbox.checked
    self.parent.raise_event("x-entry-selection-changed")
