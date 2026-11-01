from ._anvil_designer import TournamentDetailsTemplate
from anvil import *
import anvil.server


class TournamentDetails(TournamentDetailsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self._entry_options: list = []
    self._entry_tournament_id = None
    self.entry_roster_filter.items = [("Active roster", "active"), ("All roster", "all"), ("Inactive roster", "inactive")]
    self.entry_roster_filter.selected_value = "active"
    self.edit_tournament_panel.visible = False
    self.create_tournament_panel.visible = False
    self.event_status.text = ""
    self.entry_status.text = ""

  def clear(self):
    self.selected_tournament_actions.visible = False
    self.edit_tournament_panel.visible = False
    self.create_tournament_panel.visible = True
    self.build_field_panel.visible = False
    self.field_summary.visible = True
    self.field_summary.text = "No players entered yet"
    self._load_entry_options([])

  def show_create(self):
    self.selected_tournament_actions.visible = False
    self.edit_tournament_panel.visible = False
    self.create_tournament_panel.visible = True
    self.build_field_panel.visible = False
    self.field_summary.visible = False
    self.event_status.text = ""

  def load(self, entries, player_entries):
    self.selected_tournament_actions.visible = True
    self.create_tournament_panel.visible = False
    self.build_field_panel.visible = True
    self.field_summary.visible = True
    self._load_entry_options(entries)
    division_counts = {division: 0 for division in self.app.division_options}
    missing_division_count = 0
    for entry in player_entries:
      division = entry["division"]
      if division in division_counts:
        division_counts[division] += 1
      else:
        missing_division_count += 1
    non_player_count = len(entries) - len(player_entries)
    player_label = "player" if len(player_entries) == 1 else "players"
    non_player_label = "non-player" if non_player_count == 1 else "non-players"
    self.field_summary.text = (
      f"{len(player_entries)} {player_label} · {non_player_count} {non_player_label}"
      if entries
      else "No players entered yet"
    )
    if division_counts:
      division_summary = "  ·  ".join(
        f"{division}: {count}" for division, count in division_counts.items()
      )
      self.field_summary.text += f"  ·  {division_summary}"
    if missing_division_count:
      self.field_summary.text += f"  ·  {missing_division_count} unassigned"

  def _load_entry_options(self, entries):
    if self.app.current_event is None:
      self._entry_options = []
      self._entry_tournament_id = None
      self.entry_options.items = []
      self.entry_status.text = "Create or select a tournament before adding participants."
      return

    tournament_id = self.app.current_event.get_id()
    selected_ids = {
      option["golfer"].get_id() for option in self._entry_options if option["selected"]
    } if self._entry_tournament_id == tournament_id else set()
    if self._entry_tournament_id != tournament_id:
      self.entry_search.text = ""
    self._entry_tournament_id = tournament_id
    entered_ids = {entry["golfer"].get_id() for entry in entries}
    self._entry_options = [
      {
        "golfer": golfer,
        "label": golfer["name"] + (" · inactive" if not golfer["active"] else ""),
        "selected": golfer.get_id() in selected_ids,
      }
      for golfer in self.app.golfers
      if golfer.get_id() not in entered_ids
    ]
    self._refresh_entry_options()
    if not self._entry_options:
      self.entry_status.text = (
        "Add golfers to the roster first."
        if not self.app.golfers
        else "All roster golfers are already entered in this tournament."
      )
    else:
      self.entry_status.text = ""

  def _matching_entry_options(self):
    query = (self.entry_search.text or "").strip().lower()
    roster_filter = self.entry_roster_filter.selected_value or "active"
    return [option for option in self._entry_options
      if (not query or query in (option["golfer"]["name"] or "").lower())
      and (roster_filter == "all" or bool(option["golfer"]["active"]) == (roster_filter == "active"))]

  def _update_entry_selection(self):
    count = sum(1 for option in self._entry_options if option["selected"])
    matching_count = len(self._matching_entry_options())
    self.entry_selection_status.text = f"{count} selected across all filters · {matching_count} matching"
    self.add_players_button.enabled = count > 0
    self.add_non_players_button.enabled = count > 0
    self.add_players_button.text = f"Add {count} as players" if count else "Add selected as players"
    self.add_non_players_button.text = f"Add {count} as non-players" if count else "Add selected as non-players"
    self.clear_entry_selection_button.enabled = count > 0
    self.select_matching_entries_button.enabled = matching_count > 0

  def _refresh_entry_options(self):
    matches = self._matching_entry_options()
    self.entry_options.items = matches
    self.entry_empty_status.text = "" if matches else "No available participants match. Try another name or choose All roster."
    self._update_entry_selection()

  @handle("entry_search", "change")
  @handle("entry_roster_filter", "change")
  def entry_filters_change(self, **event_args):
    self._refresh_entry_options()

  @handle("entry_options", "x-entry-selection-changed")
  def entry_selection_changed(self, **event_args):
    self._update_entry_selection()

  @handle("select_matching_entries_button", "click")
  def select_matching_entries_click(self, **event_args):
    for option in self._matching_entry_options():
      option["selected"] = True
    self._refresh_entry_options()

  @handle("clear_entry_selection_button", "click")
  def clear_entry_selection_click(self, **event_args):
    for option in self._entry_options:
      option["selected"] = False
    self._refresh_entry_options()

  @handle("continue_to_field_button", "click")
  def continue_to_field_click(self, **event_args):
    self.app._show_tournament_view("field")

  @handle("edit_tournament_button", "click")
  def edit_tournament_button_click(self, **event_args):
    tournament = self.app.current_event
    if tournament is None:
      return
    self.edit_tournament_year.text = str(tournament["year"])
    self.edit_course_name.text = tournament["course"]
    self.edit_event_date.date = tournament["event_date"]
    self.edit_tournament_notes.text = tournament["notes"] or ""
    self.event_status.text = ""
    self.edit_tournament_panel.visible = True

  @handle("cancel_tournament_edit_button", "click")
  def cancel_tournament_edit_button_click(self, **event_args):
    self.edit_tournament_panel.visible = False

  @handle("save_tournament_details_button", "click")
  def save_tournament_details_button_click(self, **event_args):
    tournament = self.app.current_event
    if tournament is None:
      self.event_status.text = "Create or select a tournament first."
      return
    result = anvil.server.call(
      "update_tournament",
      tournament,
      self.edit_tournament_year.text,
      self.edit_course_name.text,
      self.edit_event_date.date,
      self.edit_tournament_notes.text,
    )
    if not result["ok"]:
      self.event_status.text = result["message"]
      return
    self.app._creating_tournament = False
    self.edit_tournament_panel.visible = False
    self.event_status.text = "Tournament details saved."
    self.app._load_events(selected=result["tournament"])

  @handle("create_tournament_button", "click")
  def create_tournament_button_click(self, **event_args):
    result = anvil.server.call(
      "create_tournament",
      self.tournament_year.text,
      self.course_name.text,
      self.event_date.date,
      self.tournament_notes.text,
    )
    if not result["ok"]:
      self.event_status.text = result["message"]
      return
    self.app._creating_tournament = False
    self.edit_tournament_panel.visible = False
    self.tournament_year.text = ""
    self.course_name.text = ""
    self.tournament_notes.text = ""
    self.event_date.date = None
    self.event_status.text = "Tournament created. Add this year's players below."
    self.app._load_events(selected=result["tournament"])

  @handle("delete_tournament_button", "click")
  def delete_tournament_button_click(self, **event_args):
    tournament = self.app.current_event
    if tournament is None:
      return

    title = f"{tournament['year']} · {tournament['course']}"
    confirmed = confirm(
      f"Delete {title}? This permanently removes the tournament, all player entries and expense details, divisions, scores, and pairings. It will also disappear from public standings.",
      title="Delete tournament",
    )
    if not confirmed:
      return

    result = anvil.server.call("delete_tournament", tournament)
    if not result["ok"]:
      self.event_status.text = result["message"]
      return
    self.app._reload_after_delete()

  def _add_selected_entries(self, is_player):
    if self.app.current_event is None:
      self.entry_status.text = "Create or select a tournament first."
      return
    selected_golfers = [option["golfer"] for option in self._entry_options if option["selected"]]
    if not selected_golfers:
      self.entry_status.text = "Select at least one participant to add."
      return
    self.add_players_button.enabled = False
    self.add_non_players_button.enabled = False
    try:
      result = anvil.server.call(
        "add_golfers_to_tournament",
        self.app.current_event,
        selected_golfers,
        is_player,
      )
    finally:
      self._update_entry_selection()
    if not result["ok"]:
      self.entry_status.text = result["message"]
      return
    self.app._load_event_data()
    added_count = result["added_count"]
    participant_label = "player" if is_player else "non-player"
    if added_count == 1:
      self.entry_status.text = f"{participant_label.capitalize()} added to this year's tournament."
    else:
      self.entry_status.text = f"{added_count} {participant_label}s added to this year's tournament."
    skipped_count = result.get("already_entered_count", 0)
    if skipped_count:
      self.entry_status.text += f" {skipped_count} already entered were skipped."

  @handle("add_players_button", "click")
  def add_players_button_click(self, **event_args):
    self._add_selected_entries(True)

  @handle("add_non_players_button", "click")
  def add_non_players_button_click(self, **event_args):
    self._add_selected_entries(False)
