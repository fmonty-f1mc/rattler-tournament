from ._anvil_designer import PublicStandingsTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
import anvil.users


class PublicStandings(PublicStandingsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    if anvil.users.get_user() is not None:
      self.sign_in_button.text = "Committee dashboard"
    self.tournaments = anvil.server.call("get_public_tournament_standings")
    self.tournament_picker.items = [
      (tournament["title"], tournament)
      for tournament in self.tournaments
    ]
    self.tournament_picker.visible = bool(self.tournaments)
    self.tournament_label.visible = bool(self.tournaments)
    self.tournament_rows.items = []
    self._expense_participants = []
    self.empty_state.visible = not self.tournaments
    if self.tournaments:
      self.tournament_picker.selected_value = self.tournaments[0]
    self._show_selected_tournament()
    self._show_public_tab("news")

  def _show_public_tab(self, name):
    for tab_name, panel, button in (
      ("news", self.news_section, self.news_tab_button),
      ("standings", self.standings_section, self.standings_tab_button),
      ("expenses", self.expenses_section, self.expenses_tab_button),
    ):
      panel.visible = name == tab_name
      button.role = (
        "tournament-subtab-active" if name == tab_name else "tournament-subtab"
      )

  def _show_selected_tournament(self):
    tournament = self.tournament_picker.selected_value
    self.tournament_rows.items = [tournament] if tournament else []
    self.news_posts = tournament["news_posts"] if tournament else []
    self.news_rows.items = self.news_posts
    self.news_empty_state.visible = not self.news_posts
    self.news_empty_state.text = (
      "No news has been posted for this tournament yet."
      if tournament
      else "No tournaments have been added yet."
    )
    self._load_selected_tournament_expenses(tournament)

  @staticmethod
  def _money(value):
    return "${:,.2f}".format(value or 0)

  def _load_selected_tournament_expenses(self, tournament):
    budget = tournament["budget_summary"] if tournament else None
    self.budget_total.text = self._money(budget["total"] if budget else 0)
    self.budget_paid.text = self._money(budget["paid"] if budget else 0)
    self.budget_balance.text = self._money(budget["balance"] if budget else 0)
    self._expense_participants = budget["participants"] if budget else []
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
    if not self.tournaments:
      self.no_budget_participants_state.text = "No tournaments have been added yet."
    elif not total_count:
      self.no_budget_participants_state.text = "No participant expense details have been added."
    else:
      self.no_budget_participants_state.text = "No participants match these filters."

  @handle("tournament_picker", "change")
  def tournament_picker_change(self, **event_args):
    self._show_selected_tournament()

  @handle("standings_tab_button", "click")
  def standings_tab_button_click(self, **event_args):
    self._show_public_tab("standings")

  @handle("news_tab_button", "click")
  def news_tab_button_click(self, **event_args):
    self._show_public_tab("news")

  @handle("expenses_tab_button", "click")
  def expenses_tab_button_click(self, **event_args):
    self._show_public_tab("expenses")

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

  @handle("sign_in_button", "click")
  def sign_in_button_click(self, **event_args):
    if anvil.users.get_user() is not None:
      open_form("Form1")
      return
    user = anvil.users.login_with_form(
      show_signup_option=True,
      allow_cancel=True,
    )
    if user is not None:
      open_form("Form1")
