from ._anvil_designer import StandingsTemplate
from anvil import *
import anvil.server


class Standings(StandingsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self._overall_standings = []
    self._active_standings = []
    self.standings_scope_picker.items = [("Overall", "overall")]
    self.standings_scope_picker.selected_value = "overall"
    self.standings_sort_by.items = [("Net", "net"), ("Gross", "gross")]
    self.standings_sort_by.selected_value = "net"
    self.standings_status.text = ""

  def clear(self):
    self.standings_scope_picker.items = [("Overall", "overall")]
    self.standings_scope_picker.selected_value = "overall"
    self._overall_standings = []
    self._active_standings = []
    self.standings_rows.items = []
    self.standings_status.text = "Create or select a tournament to see standings."

  def load(self, tournament):
    selected_scope = self.standings_scope_picker.selected_value or "overall"
    scopes = [("Overall", "overall")] + [
      ("Division: " + division, "division:" + division)
      for division in self.app.division_options
    ]
    self.standings_scope_picker.items = scopes
    if selected_scope != "overall" and selected_scope not in [
      "division:" + division for division in self.app.division_options
    ]:
      selected_scope = "overall"
    self.standings_scope_picker.selected_value = selected_scope
    self._overall_standings = anvil.server.call("get_net_standings", tournament)
    self._load_standings()

  def _load_standings(self):
    if self.app.current_event is None:
      self._active_standings = []
      self.standings_rows.items = []
      self.standings_status.text = "Create or select a tournament to see standings."
      return

    scope = self.standings_scope_picker.selected_value or "overall"
    if scope == "overall":
      self._active_standings = self._overall_standings
    else:
      self._active_standings = anvil.server.call(
        "get_division_standings",
        self.app.current_event,
        scope[len("division:"):],
      )
    self._show_standings()
    if self._active_standings:
      self.standings_status.text = ""
    elif scope == "overall":
      self.standings_status.text = "No scores have been posted for this tournament yet."
    else:
      self.standings_status.text = "No scores have been posted for this division yet."

  def _show_standings(self):
    self.standings_rows.items = self._sort_standings(
      self._active_standings,
      self.standings_sort_by.selected_value,
    )

  def _sort_standings(self, rows, sort_by):
    sort_by = sort_by or "net"
    other_score = "gross" if sort_by == "net" else "net"
    sorted_rows = sorted(
      rows,
      key=lambda row: (
        row[sort_by],
        row[other_score],
        row["player_name"].lower(),
      ),
    )
    return [dict(row, rank=index + 1) for index, row in enumerate(sorted_rows)]

  @handle("standings_scope_picker", "change")
  def standings_scope_picker_change(self, **event_args):
    self._load_standings()

  @handle("standings_sort_by", "change")
  def standings_sort_by_change(self, **event_args):
    self._show_standings()
