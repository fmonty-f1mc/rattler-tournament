from ._anvil_designer import FoursomeRowTemplate
from anvil import *


class FoursomeRow(FoursomeRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self._score_drafts = self.item["score_drafts"]
    for slot in range(1, 5):
      player = getattr(self, f"player_{slot}")
      player.items = self.item["entry_options"]
      player.selected_value = self.item[f"player_{slot}"]
    self.score_rows.items = self._score_row_items()

  def _selected_entries(self):
    return [
      self.item[f"player_{slot}"]
      for slot in range(1, 5)
      if self.item[f"player_{slot}"] is not None
    ]

  def _capture_score_drafts(self):
    for score_row in self.score_rows.get_components():
      item = getattr(score_row, "item")
      entry = item["entry"]
      self._score_drafts[entry.get_id()] = getattr(score_row, "gross_box").text

  def _score_row_items(self):
    return [
      {
        "entry": entry,
        "gross_18": self._score_drafts.get(entry.get_id(), ""),
      }
      for entry in self._selected_entries()
    ]

  def _grouping_changed(self, slot):
    self._capture_score_drafts()
    self.item[f"player_{slot}"] = getattr(self, f"player_{slot}").selected_value
    self.score_rows.items = self._score_row_items()
    self.parent.raise_event(
      "x-grouping-changed",
      score_drafts=self._score_drafts,
    )

  @handle("score_rows", "x-score-changed")
  def score_rows_score_changed(self, entry, gross, **event_args):
    self._score_drafts[entry.get_id()] = gross
    self.parent.raise_event(
      "x-round-one-score-changed",
      entry=entry,
      gross=gross,
    )

  @handle("player_1", "change")
  def player_1_change(self, **event_args):
    self._grouping_changed(1)

  @handle("player_2", "change")
  def player_2_change(self, **event_args):
    self._grouping_changed(2)

  @handle("player_3", "change")
  def player_3_change(self, **event_args):
    self._grouping_changed(3)

  @handle("player_4", "change")
  def player_4_change(self, **event_args):
    self._grouping_changed(4)
