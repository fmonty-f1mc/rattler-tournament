from ._anvil_designer import RoundTwoScoreRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class RoundTwoScoreRow(RoundTwoScoreRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.score_box.text = self._display_score(self.item["gross_9"])

  @staticmethod
  def _display_score(value):
    return "" if value is None or value <= 0 else str(value)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-round-two-score",
      entry=self.item,
      score=self.score_box.text,
    )
