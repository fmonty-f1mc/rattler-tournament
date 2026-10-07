from ._anvil_designer import ScoreRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class ScoreRow(ScoreRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.gross_box.text = self._display_score(self.item.get("gross_18"))

  @staticmethod
  def _display_score(value):
    if value is None or not str(value).strip():
      return ""
    try:
      return "" if float(value) <= 0 else str(value)
    except (TypeError, ValueError):
      return str(value)

  @handle("gross_box", "change")
  def gross_box_change(self, **event_args):
    self.item["gross_18"] = self.gross_box.text
    self.parent.raise_event(
      "x-score-changed",
      entry=self.item["entry"],
      gross=self.gross_box.text,
    )
