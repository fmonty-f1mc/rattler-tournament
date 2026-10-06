from ._anvil_designer import ScoreRowTemplate
from anvil import *


class ScoreRow(ScoreRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.gross_box.text = self._display_score(self.item["gross_18"])
    self.net_box.text = self._display_score(self.item["net_18"])

  @staticmethod
  def _display_score(value):
    return "" if value is None or value <= 0 else str(value)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-entry-scores",
      entry=self.item,
      gross=self.gross_box.text,
      net=self.net_box.text,
    )
