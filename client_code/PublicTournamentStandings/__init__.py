from ._anvil_designer import PublicTournamentStandingsTemplate
from anvil import *


class PublicTournamentStandings(PublicTournamentStandingsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.tournament_title.text = self.item["title"]
    standings = self.item["standings"]
    self.standings_rows.items = standings
    self.no_scores_state.visible = not standings
    self.divisions = self.item["divisions"]
    self.division_picker.items = [
      (division["name"], division)
      for division in self.divisions
    ]
    self.division_picker.visible = bool(self.divisions)
    self.division_label.visible = bool(self.divisions)
    self.division_empty_state.visible = not self.divisions
    if self.divisions:
      self.division_picker.selected_value = self.divisions[0]
    self._show_selected_division()

  def _show_selected_division(self):
    division = self.division_picker.selected_value
    rows = division["standings"] if division else []
    self.division_rows.items = rows
    self.division_empty_state.visible = not rows
    self.division_empty_state.text = (
      "No scores have been posted for this division yet."
      if division
      else "No divisions are set up for this tournament yet."
    )

  @handle("division_picker", "change")
  def division_picker_change(self, **event_args):
    self._show_selected_division()
