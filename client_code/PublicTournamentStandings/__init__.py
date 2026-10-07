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
    round_two_pairs = self.item["round_two_pairs"]
    self.round_two_pair_rows.items = round_two_pairs
    self.no_round_two_pairs_state.visible = not round_two_pairs
    budget = self.item["budget_summary"]
    self.budget_total.text = self._money(budget["total"])
    self.budget_paid.text = self._money(budget["paid"])
    self.budget_balance.text = self._money(budget["balance"])
    self._expense_participants = budget["participants"]
    self.expense_search.text = ""
    self.expense_participant_type_filter.items = [
      ("Everyone", "all"),
      ("Players", "players"),
      ("Non-players", "non_players"),
    ]
    self.expense_participant_type_filter.selected_value = "all"
    divisions = sorted(
      {
        participant["division"]
        for participant in self._expense_participants
        if participant["is_player"] and participant["division"]
      },
      key=lambda value: value.lower(),
    )
    self.expense_division_filter.items = [
      ("All divisions", "all"),
      ("Players without division", "unassigned"),
    ] + [(division, "division:" + division) for division in divisions]
    self.expense_division_filter.selected_value = "all"
    self.expense_payment_filter.items = [
      ("Any payment status", "all"),
      ("Balance due", "owing"),
      ("Paid in full", "paid"),
    ]
    self.expense_payment_filter.selected_value = "all"
    self._refresh_expense_participants()
    self._show_selected_standings()

  @staticmethod
  def _money(value):
    return "${:,.2f}".format(value or 0)

  def _matching_expense_participants(self):
    query = (self.expense_search.text or "").strip().lower()
    participant_type = self.expense_participant_type_filter.selected_value or "all"
    division_filter = self.expense_division_filter.selected_value or "all"
    payment_filter = self.expense_payment_filter.selected_value or "all"
    matches = []
    for participant in self._expense_participants:
      if query and query not in (participant["name"] or "").lower():
        continue
      if participant_type == "players" and not participant["is_player"]:
        continue
      if participant_type == "non_players" and participant["is_player"]:
        continue
      if division_filter == "unassigned" and (
        not participant["is_player"] or participant["division"]
      ):
        continue
      if division_filter.startswith("division:") and participant["division"] != division_filter[len("division:"):]:
        continue
      balance = participant["balance"] or 0
      if payment_filter == "owing" and balance <= 0:
        continue
      if payment_filter == "paid" and balance > 0:
        continue
      matches.append(participant)
    return matches

  def _refresh_expense_participants(self):
    matches = self._matching_expense_participants()
    self.budget_participant_rows.items = matches
    total_count = len(self._expense_participants)
    visible_count = len(matches)
    participant_word = "participant" if total_count == 1 else "participants"
    self.expense_filter_status.text = (
      f"Showing {visible_count} of {total_count} {participant_word}"
    )
    self.no_budget_participants_state.visible = not matches
    self.no_budget_participants_state.text = (
      "No participant expense details have been added."
      if not total_count
      else "No participants match these filters."
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

  @handle("expense_search", "change")
  def expense_search_change(self, **event_args):
    self._refresh_expense_participants()

  @handle("expense_participant_type_filter", "change")
  def expense_participant_type_filter_change(self, **event_args):
    self._refresh_expense_participants()

  @handle("expense_division_filter", "change")
  def expense_division_filter_change(self, **event_args):
    self._refresh_expense_participants()

  @handle("expense_payment_filter", "change")
  def expense_payment_filter_change(self, **event_args):
    self._refresh_expense_participants()
