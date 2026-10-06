from ._anvil_designer import PublicStandingsTemplate
from anvil import *
import anvil.server
import anvil.users


class PublicStandings(PublicStandingsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
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

  def _show_selected_tournament(self):
    tournament = self.tournament_picker.selected_value
    self.tournament_rows.items = [tournament] if tournament else []

  @handle("tournament_picker", "change")
  def tournament_picker_change(self, **event_args):
    self._show_selected_tournament()

  @handle("sign_in_button", "click")
  def sign_in_button_click(self, **event_args):
    user = anvil.users.login_with_form(
      show_signup_option=True,
      allow_cancel=True,
    )
    if user is not None:
      open_form("Form1")
