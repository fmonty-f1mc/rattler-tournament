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
    self.empty_state.visible = not self.tournaments
    if self.tournaments:
      self.tournament_picker.selected_value = self.tournaments[0]
    self._show_selected_tournament()
    self._show_public_tab("standings")

  def _show_public_tab(self, name):
    for tab_name, panel, button in (
      ("standings", self.standings_section, self.standings_tab_button),
      ("news", self.news_section, self.news_tab_button),
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

  @handle("tournament_picker", "change")
  def tournament_picker_change(self, **event_args):
    self._show_selected_tournament()

  @handle("standings_tab_button", "click")
  def standings_tab_button_click(self, **event_args):
    self._show_public_tab("standings")

  @handle("news_tab_button", "click")
  def news_tab_button_click(self, **event_args):
    self._show_public_tab("news")

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
