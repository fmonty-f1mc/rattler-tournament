from ._anvil_designer import PublicTournamentStandingsTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class PublicTournamentStandings(PublicTournamentStandingsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.tournament_title.text = self.item["title"]
    self.standings_scope_picker.items = [("Overall", "overall")] + [
      ("Division: " + division["name"], "division:" + division["name"])
      for division in self.item["divisions"]
    ]
    self.standings_scope_picker.selected_value = "overall"
    self.standings_sort_by.items = [("Net", "net"), ("Gross", "gross")]
    self.standings_sort_by.selected_value = "net"
    round_one_groups = self.item["round_one_groups"]
    self.round_one_group_rows.items = round_one_groups
    self.no_round_one_groups_state.visible = not round_one_groups
    round_two_pairs = self.item["round_two_pairs"]
    self.round_two_pair_rows.items = round_two_pairs
    self.no_round_two_pairs_state.visible = not round_two_pairs
    self._show_selected_standings()
    self._show_public_tab("standings")

  def _show_public_tab(self, name):
    for tab_name, panel, button in (
      ("round_one", self.round_one_tab, self.round_one_tab_button),
      ("standings", self.standings_tab, self.standings_tab_button),
      ("pairs", self.pairs_tab, self.pairs_tab_button),
    ):
      panel.visible = name == tab_name
      button.role = (
        "tournament-subtab-active" if name == tab_name else "tournament-subtab"
      )

  def _show_selected_standings(self):
    scope = self.standings_scope_picker.selected_value or "overall"
    if scope == "overall":
      rows = self.item["standings"]
      empty_message = "No scores have been posted for this tournament yet."
    else:
      division_name = scope[len("division:"):]
      division = next(
        (division for division in self.item["divisions"] if division["name"] == division_name),
        None,
      )
      rows = division["standings"] if division else []
      empty_message = "No scores have been posted for this division yet."
    self.standings_rows.items = self._sort_standings(
      rows,
      self.standings_sort_by.selected_value,
    )
    self.no_scores_state.visible = not rows
    self.no_scores_state.text = empty_message

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
    self._show_selected_standings()

  @handle("standings_sort_by", "change")
  def standings_sort_by_change(self, **event_args):
    self._show_selected_standings()

  @handle("standings_tab_button", "click")
  def standings_tab_button_click(self, **event_args):
    self._show_public_tab("standings")

  @handle("round_one_tab_button", "click")
  def round_one_tab_button_click(self, **event_args):
    self._show_public_tab("round_one")

  @handle("pairs_tab_button", "click")
  def pairs_tab_button_click(self, **event_args):
    self._show_public_tab("pairs")
