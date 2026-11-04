from ._anvil_designer import Form1Template
from anvil import *
import anvil.server
import anvil.users
from anvil.js.window import window


class Form1(Form1Template):
  """Startup dashboard: sign-in, navigation and shared tournament context."""

  _CREATE_TOURNAMENT_PICKER_OPTION = "__create_tournament__"

  def __init__(self, **properties):
    super().__init__(**properties)
    self.current_user = anvil.users.get_user()
    if self.current_user is None:
      open_form("PublicStandings")
      return
    self.current_user_label.text = self.current_user["email"]
    self.current_event = None
    self._creating_tournament = False
    self._player_entries = []
    for page in self._pages():
      page.initialize(self)
    self._show_view("event")
    self.expenses_page._show_budget_tab("categories")
    self._load_players()
    self._load_events()

  def _pages(self):
    """Keep page instances alive so switching tabs preserves unsaved edits."""
    return (
      self.tournament_details_page,
      self.tournament_field_page,
      self.round_one_page,
      self.standings_page,
      self.round_two_page,
      self.participant_directory_page,
      self.expenses_page,
      self.email_participants_page,
      self.news_editor_page,
      self.awards_page,
      self.imports_page,
    )

  def _load_event_data(self, capture_field_detail_drafts=True):
    """Refresh each page from the shared tournament selection."""
    if capture_field_detail_drafts:
      self.tournament_field_page._capture_field_detail_drafts()
    self.news_editor_page._load_news_posts()
    if self._active_view == "awards":
      self.awards_page.load()
    self.tournament_field_page.reset_status()
    if self._creating_tournament:
      self.email_participants_page._load_email_filters(None, [])
      self.tournament_details_page.show_create()
      self.selected_tournament_name.visible = False
      return

    if self.current_event is None:
      self.selected_tournament_name.visible = False
      self.division_options = []
      self.division_choices = [("No division", "")]
      self._player_entries = []
      self.tournament_details_page.clear()
      self.tournament_field_page.clear()
      self.round_one_page.clear()
      self.standings_page.clear()
      self.round_two_page.clear()
      self.expenses_page.clear()
      self.email_participants_page.clear()
      return

    tournament = self.current_event
    self.email_participants_page._set_email_subject_default(tournament)
    self.selected_tournament_name.visible = True
    date_label = self._format_tournament_date(tournament["event_date"])
    self.selected_tournament_name.text = (
      f"{tournament['year']} · {tournament['course']}"
      + (f" · {date_label}" if date_label else "")
    )
    self.division_options = anvil.server.call("list_tournament_divisions", tournament)
    self.division_choices = [("No division", "")] + [
      (division, division) for division in self.division_options
    ]
    entries = anvil.server.call("list_tournament_entries", tournament)
    self._player_entries = [entry for entry in entries if entry["is_player"] is not False]
    self.email_participants_page._load_email_filters(tournament, entries)
    self.tournament_details_page.load(entries, self._player_entries)
    self.tournament_field_page.load(tournament, self._player_entries)
    self.round_two_page.load(tournament, self._player_entries)
    self.round_one_page.load(tournament, self._player_entries)
    if self._active_view == "standings":
      self.standings_page.load(tournament)
    self.expenses_page.load(tournament)

  @staticmethod
  def _reload_after_delete():
    window.location.reload()

  @staticmethod
  def _format_tournament_date(event_date):
    if event_date is None:
      return ""
    day = event_date.day
    suffix = "th" if 11 <= day % 100 <= 13 else {
      1: "st",
      2: "nd",
      3: "rd",
    }.get(day % 10, "th")
    month_names = (
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December",
    )
    return f"{month_names[event_date.month - 1]} {day}{suffix}, {event_date.year}"

  @handle("sign_out_button", "click")
  def sign_out_button_click(self, **event_args):
    anvil.users.logout(invalidate_client_objects=True)
    open_form("Form1")

  def _show_tournament_view(self, name):
    self._show_view(name)

  def _show_view(self, name):
    self._active_view = name
    show_tournament_context = name not in ("players", "imports")
    self.selected_tournament_name.visible = (
      show_tournament_context and not self._creating_tournament
      and self.current_event is not None
    )
    self.tournament_selection_label.visible = True
    self.event_picker.visible = True
    self.tournament_details_page.field_summary.visible = name == "event" and not self._creating_tournament
    self.tournament_details_page.visible = name == "event"
    self.tournament_field_page.visible = name == "field"
    self.round_one_page.visible = name == "round_one"
    self.standings_page.visible = name == "standings"
    self.round_two_page.visible = name == "round_two"
    self.participant_directory_page.visible = name == "players"
    self.expenses_page.visible = name == "budget"
    self.email_participants_page.visible = name == "email"
    self.news_editor_page.visible = name == "news"
    self.awards_page.visible = name == "awards"
    self.imports_page.visible = name == "imports"
    self.tournament_selection_label.visible = name != "imports"
    self.event_picker.visible = name != "imports"
    for view_name, button in (
      ("event", self.setup_nav),
      ("field", self.field_nav),
      ("round_one", self.round_one_nav),
      ("standings", self.standings_nav),
      ("round_two", self.round_two_nav),
      ("email", self.email_nav),
      ("news", self.news_nav),
      ("players", self.players_nav),
      ("awards", self.awards_nav),
      ("imports", self.imports_nav),
    ):
      button.role = (
        "tournament-subtab-active" if name == view_name else "tournament-subtab"
      )
    self.expenses_page._update_budget_navigation()
    if name == "standings":
      if self.current_event is not None and not self._creating_tournament:
        self.standings_page.load(self.current_event)
      else:
        self.standings_page.clear()
    if name == "awards":
      self.awards_page.load()
    if name == "imports":
      self.imports_page.load_history()

  def _load_players(self):
    self.golfers = anvil.server.call("list_golfers")
    self.participant_directory_page._refresh_player_rows()

  def _load_events(self, selected=None):
    tournaments = anvil.server.call("list_tournaments")
    self.event_picker.items = [
      (f"{tournament['year']} · {tournament['course']}", tournament)
      for tournament in tournaments
    ] + [
      ("Create new", self._CREATE_TOURNAMENT_PICKER_OPTION),
    ]
    selected_id = selected.get_id() if selected is not None else (
      self.current_event.get_id() if self.current_event is not None else None
    )
    self.current_event = next(
      (tournament for tournament in tournaments if tournament.get_id() == selected_id),
      tournaments[0] if tournaments else None,
    )
    self.event_picker.selected_value = (
      self.current_event
      if self.current_event is not None
      else self._CREATE_TOURNAMENT_PICKER_OPTION
    )
    self._load_event_data()

  @handle("setup_nav", "click")
  def setup_nav_click(self, **event_args):
    self._show_tournament_view("event")

  @handle("email_nav", "click")
  def email_nav_click(self, **event_args):
    self._show_tournament_view("email")

  @handle("field_nav", "click")
  def field_nav_click(self, **event_args):
    self._show_tournament_view("field")

  @handle("round_one_nav", "click")
  def round_one_nav_click(self, **event_args):
    self._show_tournament_view("round_one")

  @handle("standings_nav", "click")
  def standings_nav_click(self, **event_args):
    self._show_tournament_view("standings")

  @handle("round_two_nav", "click")
  def round_two_nav_click(self, **event_args):
    self._show_tournament_view("round_two")

  @handle("players_nav", "click")
  def players_nav_click(self, **event_args):
    self._show_view("players")

  @handle("news_nav", "click")
  def news_nav_click(self, **event_args):
    self._show_tournament_view("news")

  @handle("awards_nav", "click")
  def awards_nav_click(self, **event_args):
    self._show_view("awards")

  @handle("imports_nav", "click")
  def imports_nav_click(self, **event_args):
    self._show_view("imports")

  @handle("public_view_nav", "click")
  def public_view_nav_click(self, **event_args):
    open_form("PublicStandings")

  @handle("budget_categories_tab_button", "click")
  def budget_categories_tab_button_click(self, **event_args):
    self._show_tournament_view("budget")
    self.expenses_page._show_budget_tab("categories")

  @handle("budget_assignments_tab_button", "click")
  def budget_assignments_tab_button_click(self, **event_args):
    self._show_tournament_view("budget")
    self.expenses_page._show_budget_tab("assign")

  @handle("budget_payments_tab_button", "click")
  def budget_payments_tab_button_click(self, **event_args):
    self._show_tournament_view("budget")
    self.expenses_page._show_budget_tab("payments")

  @handle("event_picker", "change")
  def event_picker_change(self, **event_args):
    selected_value = self.event_picker.selected_value
    if selected_value == self._CREATE_TOURNAMENT_PICKER_OPTION:
      self._creating_tournament = True
      self.event_picker.selected_value = (
        self.current_event
        if self.current_event is not None
        else self._CREATE_TOURNAMENT_PICKER_OPTION
      )
      self._show_view("event")
      self._load_event_data()
      return

    if self.current_event is not None and selected_value is not None and selected_value.get_id() != self.current_event.get_id():
      self.tournament_field_page._capture_field_detail_drafts()
      if self.tournament_field_page._changed_field_items() and not confirm(
        "Switch tournaments and discard unsaved division and Rattlercap changes?",
        title="Unsaved player details",
      ):
        self.event_picker.selected_value = self.current_event
        return
    self._creating_tournament = False
    self.current_event = selected_value
    self.tournament_details_page.edit_tournament_panel.visible = False
    self._load_event_data()
