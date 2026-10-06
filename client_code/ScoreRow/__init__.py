from ._anvil_designer import ScoreRowTemplate
from anvil import *


class ScoreRow(ScoreRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.division_label.text = self.item["division"] or "Not assigned"
    handicap = self.item["handicap"]
    self.handicap_label.text = "Not assigned" if handicap is None else "{:.10g}".format(handicap)
    self.gross_box.text = self._display_score(self.item["gross_18"])
    self.net_box.enabled = False
    self._update_net_preview()

  @staticmethod
  def _display_score(value):
    return "" if value is None or value <= 0 else str(value)

  def _update_net_preview(self):
    if not self.item["division"]:
      self.net_box.text = ""
      return

    try:
      gross = float(self.gross_box.text)
    except (TypeError, ValueError):
      self.net_box.text = ""
      return

    try:
      handicap = float(self.item["handicap"])
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
    self._update_net_preview()

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-entry-scores",
      entry=self.item,
      gross=self.gross_box.text,
    )
