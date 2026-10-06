from ._anvil_designer import ScoreRowTemplate
from anvil import *


class ScoreRow(ScoreRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.division_dropdown.items = ["Division 1", "Division 2", "Division 3"]
    self.division_dropdown.selected_value = self.item["division"] or None
    self.handicap_box.text = "" if not self.item["division"] else str(self.item["handicap"])
    self.gross_box.text = self._display_score(self.item["gross_18"])
    self.net_box.enabled = False
    self._update_net_preview()

  @staticmethod
  def _display_score(value):
    return "" if value is None or value <= 0 else str(value)

  def _update_net_preview(self):
    try:
      gross = float(self.gross_box.text)
    except (TypeError, ValueError):
      self.net_box.text = ""
      return

    try:
      handicap = float(self.handicap_box.text)
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

  @handle("handicap_box", "change")
  def handicap_box_change(self, **event_args):
    self._update_net_preview()

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    self.parent.raise_event(
      "x-save-entry-scores",
      entry=self.item,
      division=self.division_dropdown.selected_value,
      handicap=self.handicap_box.text,
      gross=self.gross_box.text,
    )
