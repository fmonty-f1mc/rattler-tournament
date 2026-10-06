from ._anvil_designer import Form1Template
from anvil import *
import anvil.server


class Form1(Form1Template):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.current_event = None
    self.player_division.items = ["Division 1", "Division 2", "Division 3"]
    self.player_division.selected_value = "Division 1"
    self.event_status.text = ""
    self.entry_status.text = ""
    self.player_status.text = ""
    self.round_two_status.text = ""
    self.budget_status.text = ""
    self._show_view("event")
    self._load_players()
    self._load_events()

  def _show_view(self, name):
    self.event_section.visible = name == "event"
    self.player_section.visible = name == "players"
    self.budget_section.visible = name == "budget"

  def _load_players(self):
    self.golfers = anvil.server.call("list_golfers")
    self.player_rows.items = self.golfers

  def _load_entry_options(self, entries):
    if self.current_event is None:
      self.entry_options.items = []
      self.entry_status.text = "Create or select a tournament before adding players."
      return

    entered_ids = {entry["golfer"].get_id() for entry in entries}
    self._entry_options = [
      {
        "golfer": golfer,
        "label": f"{golfer['name']} · {golfer['division']}" + (" · inactive" if not golfer["active"] else ""),
        "selected": False,
      }
      for golfer in self.golfers
      if golfer.get_id() not in entered_ids
    ]
    self.entry_options.items = self._entry_options
    if not self._entry_options:
      self.entry_status.text = (
        "Add players to the roster first."
        if not self.golfers
        else "All roster players are already entered in this tournament."
      )
    else:
      self.entry_status.text = ""

  def _load_events(self, selected=None):
    tournaments = anvil.server.call("list_tournaments")
    self.event_picker.items = [
      (f"{tournament['year']} · {tournament['course']}", tournament)
      for tournament in tournaments
    ]
    selected_id = selected.get_id() if selected is not None else (
      self.current_event.get_id() if self.current_event is not None else None
    )
    self.current_event = next(
      (tournament for tournament in tournaments if tournament.get_id() == selected_id),
      tournaments[0] if tournaments else None,
    )
    self.event_picker.selected_value = self.current_event
    self._load_event_data()

  def _load_event_data(self):
    if self.current_event is None:
      self.current_event_title.text = "Create your first tournament"
      self.current_event_subtitle.text = "Add a year and course to get started."
      self.field_summary.text = "No players entered yet"
      self.score_rows.items = []
      self.standings_rows.items = []
      self.round_two_rows.items = []
      self.budget_rows.items = []
      self.budget_total.text = "$0.00"
      self.budget_paid.text = "$0.00"
      self.budget_balance.text = "$0.00"
      self.budget_accommodated.text = "0 players"
      self.round_two_status.text = ""
      self._load_entry_options([])
      return

    tournament = self.current_event
    self.current_event_title.text = f"{tournament['year']} · {tournament['course']}"
    event_date = tournament["event_date"]
    notes = tournament["notes"]
    details = str(event_date) if event_date else "Date not set"
    if notes:
      details = f"{details} · {notes}"
    self.current_event_subtitle.text = details

    entries = anvil.server.call("list_tournament_entries", tournament)
    self._load_entry_options(entries)
    self.score_rows.items = entries
    self.round_two_rows.items = entries
    self.budget_rows.items = entries
    division_counts = {"Division 1": 0, "Division 2": 0, "Division 3": 0}
    for entry in entries:
      division_counts[entry["division"]] += 1
    self.field_summary.text = (
      f"{len(entries)} players  ·  Division 1: {division_counts['Division 1']}  ·  "
      f"Division 2: {division_counts['Division 2']}  ·  Division 3: {division_counts['Division 3']}"
    ) if entries else "No players entered yet"

    self.standings_rows.items = anvil.server.call("get_net_standings", tournament)
    self.round_two_status.text = ""

    summary = anvil.server.call("get_budget_summary", tournament)
    self.budget_total.text = self._money(summary["total"])
    self.budget_paid.text = self._money(summary["paid"])
    self.budget_balance.text = self._money(summary["balance"])
    self.budget_accommodated.text = f"{summary['accommodated']} of {summary['participants']} players"

  @staticmethod
  def _money(value):
    return "${:,.2f}".format(value or 0)

  @handle("event_nav", "click")
  def event_nav_click(self, **event_args):
    self._show_view("event")

  @handle("players_nav", "click")
  def players_nav_click(self, **event_args):
    self._show_view("players")

  @handle("budget_nav", "click")
  def budget_nav_click(self, **event_args):
    self._show_view("budget")

  @handle("event_picker", "change")
  def event_picker_change(self, **event_args):
    self.current_event = self.event_picker.selected_value
    self._load_event_data()

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
    self.tournament_year.text = ""
    self.course_name.text = ""
    self.tournament_notes.text = ""
    self.event_date.date = None
    self.event_status.text = "Tournament created. Add this year's players below."
    self._load_events(selected=result["tournament"])

  @handle("add_entry_button", "click")
  def add_entry_button_click(self, **event_args):
    if self.current_event is None:
      self.entry_status.text = "Create or select a tournament first."
      return
    selected_golfers = [option["golfer"] for option in self._entry_options if option["selected"]]
    result = anvil.server.call(
      "add_golfers_to_tournament",
      self.current_event,
      selected_golfers,
    )
    if not result["ok"]:
      self.entry_status.text = result["message"]
      return
    self._load_event_data()
    added_count = result["added_count"]
    if added_count == 1:
      self.entry_status.text = "Player added to this year's field."
    else:
      self.entry_status.text = f"{added_count} players added to this year's field."
    skipped_count = result.get("already_entered_count", 0)
    if skipped_count:
      self.entry_status.text += f" {skipped_count} already entered were skipped."

  @handle("create_player_button", "click")
  def create_player_button_click(self, **event_args):
    result = anvil.server.call(
      "create_golfer",
      self.player_name.text,
      self.player_division.selected_value,
      self.player_handicap.text,
    )
    if not result["ok"]:
      self.player_status.text = result["message"]
      return
    self.player_name.text = ""
    self.player_handicap.text = ""
    self.player_status.text = "Player added to the roster."
    self._load_players()
    self._load_event_data()

  @handle("player_rows", "x-toggle-player")
  def player_rows_toggle_player(self, golfer, active, **event_args):
    result = anvil.server.call("set_golfer_active", golfer, active)
    if not result["ok"]:
      self.player_status.text = result["message"]
      return
    self.player_status.text = "Roster updated."
    self._load_players()
    self._load_event_data()

  @handle("player_rows", "x-save-player")
  def player_rows_save_player(self, golfer, division, handicap, **event_args):
    result = anvil.server.call("update_golfer", golfer, division, handicap)
    if not result["ok"]:
      self.player_status.text = result["message"]
      return
    self.player_status.text = "Roster details updated. Existing tournament handicap snapshots were kept."
    self._load_players()
    self._load_event_data()

  @handle("score_rows", "x-save-entry-scores")
  def score_rows_save_entry_scores(self, entry, gross, **event_args):
    result = anvil.server.call("save_round_one_scores", entry, gross)
    if not result["ok"]:
      self.event_status.text = result["message"]
      return
    self.event_status.text = f"Round-one score saved for {entry['golfer']['name']}. Net: {result['net']}."
    self._load_event_data()

  @handle("round_two_rows", "x-save-round-two-score")
  def round_two_rows_save_score(self, entry, score, **event_args):
    result = anvil.server.call("save_round_two_score", entry, score)
    if not result["ok"]:
      self.round_two_status.text = result["message"]
      return
    self._load_event_data()
    self.round_two_status.text = f"Second-round score saved for {entry['golfer']['name']}."

  @handle("budget_rows", "x-save-entry-budget")
  def budget_rows_save_entry_budget(
    self,
    entry,
    accommodation,
    lodging,
    golf,
    travel,
    other,
    paid,
    **event_args,
  ):
    result = anvil.server.call(
      "save_entry_budget",
      entry,
      accommodation,
      lodging,
      golf,
      travel,
      other,
      paid,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.budget_status.text = f"Budget updated for {entry['golfer']['name']}."
    self._load_event_data()
