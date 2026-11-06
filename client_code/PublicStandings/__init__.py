from ._anvil_designer import PublicStandingsTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
import anvil.users

# This documented exception is missing from older client API stubs.
RuntimeUnavailableError = getattr(anvil.server, "RuntimeUnavailableError")


class PublicStandings(PublicStandingsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.tournaments = []
    self._tournaments_loaded = False
    self._current_tournament = None
    self._loading = False
    self._active_public_tab = "news"
    self.tournament_picker.items = []
    self.tournament_picker.visible = False
    self.tournament_label.visible = False
    self._render_tournament(None)
    self._show_public_tab("news")

  def _show_public_tab(self, name):
    if self._loading:
      return
    self._active_public_tab = name
    self._update_public_sections()
    self._load_public_data()

  def _update_public_sections(self):
    ready = self._tournaments_loaded and (
      not self.tournaments or self._current_tournament is not None
    )
    for tab_name, panel, button in (
      ("news", self.news_section, self.news_tab_button),
      ("standings", self.standings_section, self.standings_tab_button),
      ("awards", self.awards_section, self.awards_tab_button),
    ):
      panel.visible = self._active_public_tab == tab_name and ready
      button.role = (
        "tournament-subtab-active"
        if self._active_public_tab == tab_name else "tournament-subtab"
      )

  def _load_public_data(self):
    if self._loading:
      return
    self._loading = True
    self.load_status.text = "Loading tournament data…"
    self.load_status.visible = True
    self.retry_button.visible = False
    controls = (
      self.tournament_picker, self.news_tab_button, self.standings_tab_button,
      self.awards_tab_button, self.retry_button,
      self.sign_in_button,
    )
    for control in controls:
      control.enabled = False
    try:
      if not self._tournaments_loaded:
        if anvil.users.get_user() is not None:
          self.sign_in_button.text = "Committee dashboard"
        self.tournaments = anvil.server.call("list_public_tournaments")
        self.tournament_picker.items = [
          (tournament["title"], tournament["id"])
          for tournament in self.tournaments
        ]
        self.tournament_picker.visible = bool(self.tournaments)
        self.tournament_label.visible = bool(self.tournaments)
        self.tournament_picker.selected_value = (
          self.tournaments[0]["id"] if self.tournaments else None
        )
        self._tournaments_loaded = True
      tournament_id = self.tournament_picker.selected_value
      if tournament_id is not None:
        if self._current_tournament is None:
          tournament = anvil.server.call(
            "get_public_tournament_standings", tournament_id
          )
          if tournament is None:
            self._tournament_unavailable()
            return
          self._current_tournament = tournament
          self._render_tournament(tournament)
      else:
        self._render_tournament(None)
      self.load_status.visible = False
    except RuntimeUnavailableError:
      self.load_status.text = "Tournament data is temporarily unavailable. Please retry."
      self.retry_button.visible = True
    finally:
      self._loading = False
      for control in controls:
        control.enabled = True
      self._update_public_sections()

  def _tournament_unavailable(self):
    # A committee member may delete a tournament after the picker was loaded.
    self._tournaments_loaded = False
    self._current_tournament = None
    self._render_tournament(None)
    self.load_status.text = "This tournament is no longer available. Retry to refresh the list."
    self.retry_button.visible = True

  def _show_selected_tournament(self):
    if self._loading:
      return
    self._current_tournament = None
    self._render_tournament(None)
    self._update_public_sections()
    self._load_public_data()

  def _render_tournament(self, tournament):
    self.selected_tournament_name.text = (
      tournament["title"]
      + (f" · {tournament['date_label']}" if tournament["date_label"] else "")
      if tournament else ""
    )
    self.selected_tournament_name.visible = tournament is not None
    self.tournament_rows.items = [tournament] if tournament else []
    self.empty_state.visible = not self.tournaments
    self.news_posts = tournament["news_posts"] if tournament else []
    self.news_rows.items = self.news_posts
    self.news_empty_state.visible = not self.news_posts
    self.news_empty_state.text = (
      "No news has been posted for this tournament yet."
      if tournament
      else "No tournaments have been added yet."
    )
    awards = tournament["awards"] if tournament else []
    self.award_rows.items = awards
    self.awards_empty_state.visible = not awards
    self.awards_empty_state.text = (
      "No award winners have been recorded for this tournament yet."
      if tournament else "No tournaments have been added yet."
    )

  @handle("tournament_picker", "change")
  def tournament_picker_change(self, **event_args):
    self._show_selected_tournament()

  @handle("retry_button", "click")
  def retry_button_click(self, **event_args):
    self._load_public_data()

  @handle("standings_tab_button", "click")
  def standings_tab_button_click(self, **event_args):
    self._show_public_tab("standings")

  @handle("news_tab_button", "click")
  def news_tab_button_click(self, **event_args):
    self._show_public_tab("news")

  @handle("awards_tab_button", "click")
  def awards_tab_button_click(self, **event_args):
    self._show_public_tab("awards")

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
