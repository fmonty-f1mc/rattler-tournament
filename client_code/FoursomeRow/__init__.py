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
      self._refresh_gross_score(slot)

  @staticmethod
  def _display_score(value):
    if value is None or not str(value).strip():
      return ""
    try:
      return "" if float(value) <= 0 else str(value)
    except (TypeError, ValueError):
      return str(value)

  def _refresh_gross_score(self, slot):
    entry = self.item[f"player_{slot}"]
    gross_box = getattr(self, f"gross_score_{slot}")
    gross_box.enabled = entry is not None
    if entry is None:
      gross_box.text = ""
      return
    value = self._score_drafts.get(entry.get_id(), entry["gross_18"])
    gross_box.text = self._display_score(value)

  def _capture_score_drafts(self):
    for slot in range(1, 5):
      entry = self.item[f"player_{slot}"]
      if entry is not None:
        self._score_drafts[entry.get_id()] = getattr(
          self, f"gross_score_{slot}"
        ).text

  def _capture_group_details(self):
    group_name = (self.group_name_box.text or "").strip()
    self.item["group_label"] = group_name
    self.item["tee_time"] = (self.tee_time_box.text or "").strip()

  def _group_details_changed(self):
    self._capture_group_details()
    self.parent.raise_event(
      "x-grouping-changed",
      score_drafts=self._score_drafts,
    )

  def _grouping_changed(self, slot):
    self._capture_score_drafts()
    self._capture_group_details()
    self.item[f"player_{slot}"] = getattr(self, f"player_{slot}").selected_value
    self._refresh_gross_score(slot)
    self.parent.raise_event(
      "x-grouping-changed",
      score_drafts=self._score_drafts,
    )

  def _gross_score_changed(self, slot):
    entry = self.item[f"player_{slot}"]
    if entry is None:
      return
    gross = getattr(self, f"gross_score_{slot}").text
    self._score_drafts[entry.get_id()] = gross
    self.parent.raise_event(
      "x-round-one-score-changed",
      entry=entry,
      gross=gross,
    )

  @handle("save_group_button", "click")
  def save_group_button_click(self, **event_args):
    self._capture_score_drafts()
    self._capture_group_details()
    if not self.item["group_label"]:
      self.item["group_label"] = f"Group {self.item['sequence']}"
      self.group_name_box.text = self.item["group_label"]
    scores = []
    for slot in range(1, 5):
      entry = self.item[f"player_{slot}"]
      gross = getattr(self, f"gross_score_{slot}").text
      if entry is not None and gross is not None and str(gross).strip():
        scores.append({"entry": entry, "gross": gross})
    self.parent.raise_event(
      "x-save-round-one-group",
      group_label=self.item["group_label"],
      tee_time=self.item["tee_time"],
      scores=scores,
    )

  @handle("group_name_box", "change")
  def group_name_box_change(self, **event_args):
    self._group_details_changed()

  @handle("tee_time_box", "change")
  def tee_time_box_change(self, **event_args):
    self._group_details_changed()

  @handle("player_1", "change")
  def player_1_change(self, **event_args):
    self._grouping_changed(1)

  @handle("gross_score_1", "change")
  def gross_score_1_change(self, **event_args):
    self._gross_score_changed(1)

  @handle("player_2", "change")
  def player_2_change(self, **event_args):
    self._grouping_changed(2)

  @handle("gross_score_2", "change")
  def gross_score_2_change(self, **event_args):
    self._gross_score_changed(2)

  @handle("player_3", "change")
  def player_3_change(self, **event_args):
    self._grouping_changed(3)

  @handle("gross_score_3", "change")
  def gross_score_3_change(self, **event_args):
    self._gross_score_changed(3)

  @handle("player_4", "change")
  def player_4_change(self, **event_args):
    self._grouping_changed(4)

  @handle("gross_score_4", "change")
  def gross_score_4_change(self, **event_args):
    self._gross_score_changed(4)
