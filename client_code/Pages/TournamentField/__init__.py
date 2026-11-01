from ._anvil_designer import TournamentFieldTemplate
from anvil import *
import anvil.server


class TournamentField(TournamentFieldTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  _CREATE_DIVISION_PICKER_OPTION = "__create_division__"

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self._field_detail_drafts = {}
    self._field_detail_items = []
    self._selected_field_entry_ids = set()
    self._field_selection_tournament_id = None
    self._division_selection = None
    self.field_status.text = ""
    self.division_status.text = ""
    self.create_division_panel.visible = False

  def clear(self):
    self._field_detail_items = []
    self.field_search_box.text = ""
    self.field_search_box.enabled = False
    self.field_division_filter.items = [("All divisions", "all")]
    self.field_division_filter.selected_value = "all"
    self.field_division_filter.enabled = False
    self.field_search_status.text = ""
    self.field_selection_status.text = "0 selected · 0 matching · 0 players"
    self.select_matching_field_players_button.enabled = False
    self.clear_matching_field_players_button.enabled = False
    self.division_dropdown.items = []
    self.division_dropdown.selected_value = None
    self.division_dropdown.enabled = False
    self.apply_division_to_selected_button.enabled = False
    self.bulk_handicap_input.enabled = False
    self.apply_handicap_to_selected_button.enabled = False
    self.remove_selected_field_entries_button.enabled = False
    self._division_selection = None
    self.create_division_panel.visible = False
    self.delete_division_button.enabled = False
    self.field_rows.items = []
    self._selected_field_entry_ids = set()
    self._field_selection_tournament_id = None

  def reset_status(self):
    self.field_status.text = ""
    self.division_status.text = ""
    self.create_division_panel.visible = False

  def load(self, tournament, player_entries):
    division_values = [value for _, value in self.app.division_choices]
    if self._division_selection not in division_values:
      self._division_selection = None
    self.division_dropdown.items = (
      [("Choose a division", None)] + self.app.division_choices +
      [("Create new division…", self._CREATE_DIVISION_PICKER_OPTION)]
    )
    self.division_dropdown.selected_value = self._division_selection
    self.division_dropdown.enabled = True
    self.delete_division_button.enabled = self._division_selection in self.app.division_options
    tournament_id = tournament.get_id()
    if self._field_selection_tournament_id != tournament_id:
      self._selected_field_entry_ids = set()
      self._field_selection_tournament_id = tournament_id
      self.field_search_box.text = ""
      self.field_division_filter.selected_value = "all"
    self.field_search_box.enabled = bool(player_entries)
    self.field_division_filter.enabled = bool(player_entries)
    field_division_options = [
      ("All divisions", "all"),
      ("Players without division", "unassigned"),
    ] + [
      (division, "division:" + division)
      for division in sorted(self.app.division_options, key=lambda value: value.lower())
    ]
    selected_division_filter = self.field_division_filter.selected_value or "all"
    self.field_division_filter.items = field_division_options
    self.field_division_filter.selected_value = next(
      (value for _, value in field_division_options if value == selected_division_filter),
      "all",
    )
    self.apply_division_to_selected_button.enabled = bool(player_entries)
    self.bulk_handicap_input.enabled = bool(player_entries)
    self.apply_handicap_to_selected_button.enabled = bool(player_entries)
    self.remove_selected_field_entries_button.enabled = bool(player_entries)
    self.select_matching_field_players_button.enabled = bool(player_entries)
    self.clear_matching_field_players_button.enabled = bool(player_entries)
    self.field_rows.items = []
    field_items: list = []
    for entry in player_entries:
      entry_id = entry.get_id()
      draft = self._field_detail_drafts.get(entry_id)
      if draft is None:
        division = entry["division"] or ""
        handicap = "" if entry["handicap"] is None else str(entry["handicap"])
      else:
        division = draft["division"] or ""
        handicap = draft["handicap"]
      field_items.append({
        "entry": entry,
        "division_options": self.app.division_choices,
        "division": division,
        "handicap": handicap,
        "selected": entry_id in self._selected_field_entry_ids,
      })
    self._field_detail_items = field_items
    self._refresh_field_rows()

  def _matching_field_items(self):
    query = (self.field_search_box.text or "").strip().lower()
    division_filter = self.field_division_filter.selected_value or "all"
    matches = []
    for item in self._field_detail_items:
      name = (item["entry"]["golfer"]["name"] or "").lower()
      division = (item["division"] or "").strip()
      if query and query not in name:
        continue
      if division_filter == "unassigned" and division:
        continue
      if division_filter.startswith("division:") and division != division_filter[len("division:"):]:
        continue
      matches.append(item)
    return matches

  def _sync_field_selection(self):
    self._selected_field_entry_ids = {
      item["entry"].get_id()
      for item in self._field_detail_items
      if item["selected"]
    }

  def _update_field_selection_status(self):
    self._sync_field_selection()
    selected_count = len(self._selected_field_entry_ids)
    matching_count = len(self._matching_field_items())
    total_count = len(self._field_detail_items)
    self.field_selection_status.text = (
      f"{selected_count} selected · {matching_count} matching · {total_count} players"
    )

  def _refresh_field_rows(self):
    field_items = self._matching_field_items()

    self.field_rows.items = field_items
    if not self._field_detail_items:
      self.field_search_status.text = ""
    elif not field_items:
      self.field_search_status.text = "No players match these filters."
    elif len(field_items) < len(self._field_detail_items):
      self.field_search_status.text = (
        f"Showing {len(field_items)} of {len(self._field_detail_items)} players."
      )
    else:
      self.field_search_status.text = ""
    self._update_field_selection_status()

  def _capture_field_detail_drafts(self):
    for row in self.field_rows.get_components():
      item = getattr(row, "item")
      entry = item["entry"]
      entry_id = entry.get_id()
      item["division"] = getattr(row, "division_dropdown").selected_value
      item["handicap"] = getattr(row, "handicap_box").text
      item["selected"] = getattr(row, "select_player_checkbox").checked
      self._field_detail_drafts[entry_id] = {
        "division": item["division"],
        "handicap": item["handicap"],
      }
      if item["selected"]:
        self._selected_field_entry_ids.add(entry_id)
      else:
        self._selected_field_entry_ids.discard(entry_id)

    for item in self._field_detail_items:
      entry_id = item["entry"].get_id()
      draft = self._field_detail_drafts.get(entry_id)
      if draft is not None:
        item["division"] = draft["division"]
        item["handicap"] = draft["handicap"]
      item["selected"] = entry_id in self._selected_field_entry_ids
    self._update_field_selection_status()

  def _current_field_detail_values(self):
    self._capture_field_detail_drafts()
    return [
      {
        "entry": item["entry"],
        "division": item["division"],
        "handicap": item["handicap"],
      }
      for item in self._field_detail_items
    ]

  @handle("division_dropdown", "change")
  def division_dropdown_change(self, **event_args):
    selected_division = self.division_dropdown.selected_value
    if selected_division == self._CREATE_DIVISION_PICKER_OPTION:
      self.create_division_panel.visible = True
      self.new_division_name.text = ""
      self.division_dropdown.selected_value = self._division_selection
      return

    self._division_selection = selected_division
    self.create_division_panel.visible = False
    self.delete_division_button.enabled = selected_division in self.app.division_options

  @handle("create_division_button", "click")
  def create_division_button_click(self, **event_args):
    if self.app.current_event is None:
      self.division_status.text = "Create or select a tournament first."
      return
    result = anvil.server.call(
      "create_tournament_division",
      self.app.current_event,
      self.new_division_name.text,
    )
    if not result["ok"]:
      self.division_status.text = result["message"]
      return
    self.new_division_name.text = ""
    self.create_division_panel.visible = False
    self._division_selection = result["division_name"]
    self.app._load_event_data()
    self.division_status.text = f"{result['division_name']} created for this tournament."

  @handle("delete_division_button", "click")
  def delete_division_button_click(self, **event_args):
    if self.app.current_event is None:
      self.division_status.text = "Create or select a tournament first."
      return
    division = self.division_dropdown.selected_value
    if not division:
      self.division_status.text = "Choose a division to delete."
      return
    confirmed = confirm(
      f"Delete {division}? Players assigned to it will have no division, and their scores will be kept.",
      title="Delete division",
    )
    if not confirmed:
      return

    self._capture_field_detail_drafts()
    result = anvil.server.call(
      "delete_tournament_division",
      self.app.current_event,
      division,
    )
    if not result["ok"]:
      self.division_status.text = result["message"]
      return
    self.app._reload_after_delete()

  @handle("save_field_details_button", "click")
  def save_field_details_button_click(self, **event_args):
    if self.app.current_event is None:
      self.field_status.text = "Create or select a tournament first."
      return
    entry_details = self._current_field_detail_values()
    if not entry_details:
      self.field_status.text = "Add players to this tournament before saving field details."
      return
    result = anvil.server.call(
      "save_tournament_entry_details_batch",
      self.app.current_event,
      entry_details,
    )
    if not result["ok"]:
      self.field_status.text = result["message"]
      return
    self.app._load_event_data()
    self._selected_field_entry_ids.clear()
    for item in self._field_detail_items:
      item["selected"] = False
    for row in self.field_rows.get_components():
      row_item = getattr(row, "item")
      row_item["selected"] = False
      getattr(row, "select_player_checkbox").checked = False
    self._update_field_selection_status()
    self.field_status.text = f"Division and Rattlercap saved for {result['saved_count']} players."

  @handle("field_search_box", "change")
  def field_search_box_change(self, **event_args):
    self._capture_field_detail_drafts()
    self._refresh_field_rows()

  @handle("field_division_filter", "change")
  def field_division_filter_change(self, **event_args):
    self._capture_field_detail_drafts()
    self._refresh_field_rows()

  @handle("field_rows", "x-field-player-selection-changed")
  def field_rows_selection_changed(self, **event_args):
    self._update_field_selection_status()

  @handle("select_matching_field_players_button", "click")
  def select_matching_field_players_button_click(self, **event_args):
    self._capture_field_detail_drafts()
    for item in self._matching_field_items():
      item["selected"] = True
    self._refresh_field_rows()

  @handle("clear_matching_field_players_button", "click")
  def clear_matching_field_players_button_click(self, **event_args):
    self._capture_field_detail_drafts()
    for item in self._matching_field_items():
      item["selected"] = False
    self._refresh_field_rows()

  @handle("apply_division_to_selected_button", "click")
  def apply_division_to_selected_button_click(self, **event_args):
    if self.app.current_event is None:
      self.field_status.text = "Create or select a tournament first."
      return

    division = self.division_dropdown.selected_value
    if division is None or division not in [value for _, value in self.app.division_choices]:
      self.field_status.text = "Choose a division to apply."
      return

    self._capture_field_detail_drafts()
    selected_items = [
      item for item in self._field_detail_items
      if item.get("selected")
    ]
    if not selected_items:
      self.field_status.text = "Select at least one player."
      return

    selected_ids = {item["entry"].get_id() for item in selected_items}
    for item in selected_items:
      item["division"] = division
      entry_id = item["entry"].get_id()
      draft = self._field_detail_drafts.get(entry_id) or {
        "division": item["division"],
        "handicap": item["handicap"],
      }
      draft["division"] = division
      self._field_detail_drafts[entry_id] = draft
    for row in self.field_rows.get_components():
      if getattr(row, "item")["entry"].get_id() in selected_ids:
        getattr(row, "set_division")(division)
    self._capture_field_detail_drafts()
    self._refresh_field_rows()
    division_label = division or "No division"
    self.field_status.text = (
      f"Applied {division_label} to {len(selected_items)} selected players. "
      "Save all player details to keep the changes."
    )

  @handle("apply_handicap_to_selected_button", "click")
  def apply_handicap_to_selected_button_click(self, **event_args):
    if self.app.current_event is None:
      self.field_status.text = "Create or select a tournament first."
      return

    handicap = self.bulk_handicap_input.text.strip()
    if not handicap:
      self.field_status.text = "Enter a Rattlercap to apply."
      return

    self._capture_field_detail_drafts()
    selected_items = [
      item for item in self._field_detail_items
      if item.get("selected")
    ]
    if not selected_items:
      self.field_status.text = "Select at least one player."
      return

    selected_ids = {item["entry"].get_id() for item in selected_items}
    for item in selected_items:
      item["handicap"] = handicap
      entry_id = item["entry"].get_id()
      draft = self._field_detail_drafts.get(entry_id) or {
        "division": item["division"],
        "handicap": item["handicap"],
      }
      draft["handicap"] = handicap
      self._field_detail_drafts[entry_id] = draft
    for row in self.field_rows.get_components():
      if getattr(row, "item")["entry"].get_id() in selected_ids:
        getattr(row, "set_handicap")(handicap)
    self._capture_field_detail_drafts()
    self.field_status.text = (
      f"Applied Rattlercap {handicap} to {len(selected_items)} selected players. "
      "Save all player details to keep the changes."
    )

  @handle("remove_selected_field_entries_button", "click")
  def remove_selected_field_entries_button_click(self, **event_args):
    if self.app.current_event is None:
      self.field_status.text = "Create or select a tournament first."
      return

    self._capture_field_detail_drafts()
    selected_entries = [
      item["entry"] for item in self._field_detail_items
      if item.get("selected")
    ]
    if not selected_entries:
      self.field_status.text = "Select at least one player."
      return

    player_label = "player" if len(selected_entries) == 1 else "players"
    tournament = self.app.current_event
    confirmed = confirm(
      f"Remove {len(selected_entries)} selected {player_label} from this tournament? Their scores and expense details for this tournament will be deleted. Pairings containing them will also be removed, including shared pairing scores for other players.",
      title="Remove selected players",
    )
    if not confirmed:
      return

    self._capture_field_detail_drafts()
    selected_entry_ids = [entry.get_id() for entry in selected_entries]
    removed_entry_ids = []
    for entry, entry_id in zip(selected_entries, selected_entry_ids):
      result = anvil.server.call("remove_tournament_entry", tournament, entry)
      if not result["ok"]:
        for entry_id in removed_entry_ids:
          self._field_detail_drafts.pop(entry_id, None)
          self._selected_field_entry_ids.discard(entry_id)
        if removed_entry_ids:
          self.app._load_event_data(capture_field_detail_drafts=False)
          self.field_status.text = (
            f"Removed {len(removed_entry_ids)} of {len(selected_entries)} selected {player_label}. "
            f"{result['message']}"
          )
        else:
          self.field_status.text = result["message"]
        return
      removed_entry_ids.append(entry_id)

    self.app._reload_after_delete()
