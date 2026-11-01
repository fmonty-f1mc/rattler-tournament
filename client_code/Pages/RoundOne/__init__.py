from ._anvil_designer import RoundOneTemplate
from anvil import *
import anvil.server


class RoundOne(RoundOneTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self._round_one_score_drafts = {}
    self.round_one_status.text = ""

  def clear(self):
    self._round_one_score_drafts = {}
    self.foursome_group_rows.items = []
    self.round_one_status.text = ""

  def load(self, tournament, player_entries):
    self._round_one_score_drafts = {
      entry.get_id(): (
        "" if entry["gross_18"] is None or entry["gross_18"] <= 0
        else str(entry["gross_18"])
      )
      for entry in player_entries
    }
    foursomes = anvil.server.call("get_or_create_tournament_foursomes", tournament)
    self.foursome_group_rows.items = self._foursome_group_items(
      foursomes,
      player_entries,
    )
    self.round_one_status.text = (
      "Tee times are ready. Enter gross scores in each group."
      if self.foursome_group_rows.items
      else "Add players to this tournament to create tee time groups."
    )

  def _foursome_group_items(self, foursomes, player_entries):
    entry_options = [(self._round_one_entry_label(entry), entry) for entry in player_entries]
    entry_options = [("Open slot", None)] + entry_options
    items = []
    for group in foursomes:
      entries = [
        group[f"player_{slot}"]
        for slot in range(1, 5)
        if group[f"player_{slot}"] is not None
      ]
      items.append(self._foursome_group_item(
        group["sequence"],
        group["group_label"] or f"Group {group['sequence']}",
        entries,
        entry_options,
        group["tee_time"] or "",
      ))
    return items

  @staticmethod
  def _round_one_entry_label(entry):
    name = entry["golfer"]["name"]
    division = (entry["division"] or "").strip()
    return f"{name} - {division}" if division else name

  def _foursome_group_item(self, sequence, label, entries, entry_options, tee_time=""):
    item = {
      "sequence": sequence,
      "group_label": label,
      "tee_time": tee_time,
      "entry_options": entry_options,
      "score_entries": entries,
      "score_drafts": self._round_one_score_drafts,
    }
    for slot in range(1, 5):
      item[f"player_{slot}"] = entries[slot - 1] if len(entries) >= slot else None
    return item

  def _current_round_one_scores(self):
    scores = []
    for group in self.foursome_group_rows.get_components():
      group_item = getattr(group, "item")
      for slot in range(1, 5):
        entry = group_item[f"player_{slot}"]
        if entry is None:
          continue
        gross = getattr(group, f"gross_score_{slot}").text
        self._round_one_score_drafts[entry.get_id()] = gross
        if gross is not None and str(gross).strip():
          scores.append({"entry": entry, "gross": gross})
    return scores

  def _current_foursome_assignments(self):
    assignments = []
    for group in self.foursome_group_rows.items or []:
      assignments.append({
        "group_label": group.get("group_label", ""),
        "tee_time": group.get("tee_time", ""),
        "entries": [
          group[f"player_{slot}"]
          for slot in range(1, 5)
          if group[f"player_{slot}"] is not None
        ],
      })
    return assignments

  @handle("generate_foursomes_button", "click")
  def generate_foursomes_button_click(self, **event_args):
    if self.app.current_event is None:
      self.round_one_status.text = "Create or select a tournament first."
      return
    result = anvil.server.call(
      "build_tournament_foursomes",
      self.app.current_event,
    )
    if not result["ok"]:
      self.round_one_status.text = result["message"]
      return

    self._current_round_one_scores()
    existing_groups = {
      group["sequence"]: group
      for group in self.foursome_group_rows.items or []
    }
    entry_options = [("Open slot", None)] + [
      (self._round_one_entry_label(entry), entry)
      for entry in self.app._player_entries
    ]
    group_items = []
    for grouping in result["groupings"]:
      existing_group = existing_groups.get(grouping["sequence"], {})
      group_items.append(self._foursome_group_item(
        grouping["sequence"],
        existing_group.get("group_label") or grouping["group_label"],
        grouping["entries"],
        entry_options,
        existing_group.get("tee_time") or "",
      ))
    self.foursome_group_rows.items = group_items
    self.round_one_status.text = (
      f"Preview: {result['group_count']} tee time groups generated. "
      "Edit players as needed, then save tee times and scores."
    )

  @handle("add_foursome_group_button", "click")
  def add_foursome_group_button_click(self, **event_args):
    if self.app.current_event is None:
      self.round_one_status.text = "Create or select a tournament first."
      return
    if not self.app._player_entries:
      self.round_one_status.text = "Add players to this tournament before adding groups."
      return

    self._current_round_one_scores()
    group_items = list(self.foursome_group_rows.items or [])
    entry_options = [("Open slot", None)] + [
      (entry["golfer"]["name"], entry) for entry in self.app._player_entries
    ]
    group_items.append(self._foursome_group_item(
      len(group_items) + 1,
      f"Group {len(group_items) + 1}",
      [],
      entry_options,
    ))
    self.foursome_group_rows.items = group_items
    self.round_one_status.text = (
      "Group added. Assign 1–4 players to every group, then save."
    )

  @handle("foursome_group_rows", "x-grouping-changed")
  def foursome_group_rows_grouping_changed(self, **event_args):
    for entry_id, gross in event_args.get("score_drafts", {}).items():
      self._round_one_score_drafts[entry_id] = gross
    self.round_one_status.text = "Tee time or score changes are not saved yet."

  @handle("foursome_group_rows", "x-round-one-score-changed")
  def foursome_group_rows_round_one_score_changed(self, entry, gross, **event_args):
    self._round_one_score_drafts[entry.get_id()] = gross
    self.round_one_status.text = "Tee time or score changes are not saved yet."

  @handle("foursome_group_rows", "x-save-round-one-group")
  def foursome_group_rows_save_round_one_group(self, group_label, scores, **event_args):
    if self.app.current_event is None:
      self.round_one_status.text = "Create or select a tournament first."
      return

    self._current_round_one_scores()
    grouping_result = anvil.server.call(
      "save_tournament_foursomes",
      self.app.current_event,
      self._current_foursome_assignments(),
    )
    if not grouping_result["ok"]:
      self.round_one_status.text = grouping_result["message"]
      return

    if not scores:
      self.round_one_status.text = (
        f"Tee times saved. Enter gross scores in {group_label} when ready."
      )
      return

    result = anvil.server.call(
      "save_round_one_scores_batch",
      self.app.current_event,
      scores,
    )
    if not result["ok"]:
      self.round_one_status.text = result["message"]
      return
    count = result["saved_count"]
    player_word = "player" if count == 1 else "players"
    self.round_one_status.text = (
      f"Tee times and {group_label} scores saved for {count} {player_word}."
    )
