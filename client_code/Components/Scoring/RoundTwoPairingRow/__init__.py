from ._anvil_designer import RoundTwoPairingRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class RoundTwoPairingRow(RoundTwoPairingRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.first_player.items = self.item["entry_options"]
    self.second_player.items = [("Solo (no partner)", None)] + self.item["entry_options"]
    self.first_player.selected_value = self.item["first_entry"]
    self.second_player.selected_value = self.item["second_entry"]
    self.score_box.text = self._display_score(self.item["score_9"])

  @staticmethod
  def _display_score(value):
    return "" if value is None or value <= 0 else str(value)

  def _pairing_changed(self):
    self.item["first_entry"] = self.first_player.selected_value
    self.item["second_entry"] = self.second_player.selected_value
    self.item["score_9"] = ""
    self.item["score_changed"] = True
    self.score_box.text = ""
    first_name = self.first_player.selected_value["golfer"]["name"]
    second_entry = self.second_player.selected_value
    self.item["pair_label"] = (
      f"{first_name} · solo"
      if second_entry is None
      else f"{first_name} + {second_entry['golfer']['name']}"
    )
    self.parent.raise_event("x-pairing-changed")

  @handle("score_box", "change")
  def score_box_change(self, **event_args):
    self.item["score_9"] = self.score_box.text
    self.item["score_changed"] = True
    self.parent.raise_event("x-pairing-changed")

  @handle("first_player", "change")
  def first_player_change(self, **event_args):
    self._pairing_changed()

  @handle("second_player", "change")
  def second_player_change(self, **event_args):
    self._pairing_changed()
