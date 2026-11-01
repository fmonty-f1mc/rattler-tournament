from ._anvil_designer import TournamentDetailsTemplate
from anvil import *
import anvil.server


class TournamentDetails(TournamentDetailsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
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
      self.entry_options.items = []
      self.entry_status.text = "Create or select a tournament before adding participants."
      return

    entered_ids = {entry["golfer"].get_id() for entry in entries}
    self._entry_options = [
      {
        "golfer": golfer,
        "label": golfer["name"] + (" · inactive" if not golfer["active"] else ""),
        "selected": False,
      }
      for golfer in self.app.golfers
      if golfer.get_id() not in entered_ids
    ]
    self.entry_options.items = self._entry_options
    if not self._entry_options:
      self.entry_status.text = (
        "Add golfers to the roster first."
        if not self.app.golfers
        else "All roster golfers are already entered in this tournament."
      )
    else:
      self.entry_status.text = ""

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
    result = anvil.server.call(
      "add_golfers_to_tournament",
      self.app.current_event,
      selected_golfers,
      is_player,
    )
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
