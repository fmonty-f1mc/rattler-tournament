from ._anvil_designer import ScoreRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class ScoreRow(ScoreRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    entry = self.item["entry"]
    self.division_label.text = entry["division"] or "No division"
    handicap = entry["handicap"]
    self.handicap_label.text = "Not assigned" if handicap is None else "{:.10g}".format(handicap)
    self.gross_box.text = self._display_score(self.item.get("gross_18"))
    self.net_box.enabled = False
    self._update_net_preview()

  @staticmethod
  def _display_score(value):
    if value is None or not str(value).strip():
      return ""
    try:
      return "" if float(value) <= 0 else str(value)
    except (TypeError, ValueError):
      return str(value)

  def _update_net_preview(self):
    try:
      gross = float(self.gross_box.text)
    except (TypeError, ValueError):
      self.net_box.text = ""
      return

    try:
      handicap = float(self.item["entry"]["handicap"])
    except (TypeError, ValueError):
      self.net_box.text = ""
      return

    if not gross > 0 or gross % 1 != 0:
      self.net_box.text = ""
      return

    net = round(gross - handicap, 10)
    self.net_box.text = "{:.10g}".format(net)

  @handle("gross_box", "change")
  def gross_box_change(self, **event_args):
    self.item["gross_18"] = self.gross_box.text
    self._update_net_preview()
    self.parent.raise_event(
      "x-score-changed",
      entry=self.item["entry"],
      gross=self.gross_box.text,
    )
