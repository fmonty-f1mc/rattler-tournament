from ._anvil_designer import ParticipantDirectoryTemplate
from anvil import *
import anvil.server


class ParticipantDirectory(ParticipantDirectoryTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self.player_status.text = ""
    self._show_player_add_mode(None)

  def _refresh_player_rows(self):
    query = (self.player_search.text or "").strip().lower()
    email_unlisted = self.email_unlisted_filter.checked
    phone_unlisted = self.phone_unlisted_filter.checked
    matches = []

    for golfer in self.app.golfers:
      name = (golfer["name"] or "").lower()
      email = (golfer["email"] or "").strip()
      phone = (golfer["phone"] or "").strip()
      searchable_text = " ".join((name, email.lower(), phone.lower()))

      if query and query not in searchable_text:
        continue
      if email_unlisted and email:
        continue
      if phone_unlisted and phone:
        continue
      matches.append(golfer)

    self.player_rows.items = matches
    self.player_filter_status.text = (
      f"Showing {len(matches)} of {len(self.app.golfers)} participants"
    )
    self.no_player_matches.visible = not matches
    self.no_player_matches.text = (
      "No participants in the roster yet."
      if not self.app.golfers else "No participants match these filters."
    )

  @handle("player_search", "change")
  def player_search_change(self, **event_args):
    self._refresh_player_rows()

  @handle("email_unlisted_filter", "change")
  def email_unlisted_filter_change(self, **event_args):
    self._refresh_player_rows()

  @handle("phone_unlisted_filter", "change")
  def phone_unlisted_filter_change(self, **event_args):
    self._refresh_player_rows()

  def _show_player_add_mode(self, mode):
    self.player_add_options.visible = mode is None
    self.player_create_panel.visible = mode == "individual"
    self.player_import_panel.visible = mode == "bulk"
    self.player_status.text = ""

  @handle("open_individual_player_add_button", "click")
  def open_individual_player_add_button_click(self, **event_args):
    self._show_player_add_mode("individual")

  @handle("open_bulk_player_add_button", "click")
  def open_bulk_player_add_button_click(self, **event_args):
    self._show_player_add_mode("bulk")

  @handle("close_individual_player_add_button", "click")
  def close_individual_player_add_button_click(self, **event_args):
    self._show_player_add_mode(None)

  @handle("close_bulk_player_add_button", "click")
  def close_bulk_player_add_button_click(self, **event_args):
    self._show_player_add_mode(None)

  @handle("create_player_button", "click")
  def create_player_button_click(self, **event_args):
    result = anvil.server.call(
      "create_golfer",
      self.player_name.text,
      self.player_email.text,
      self.player_phone.text,
      self.player_city.text,
      self.player_state.text,
      self.player_handicap.text,
    )
    if not result["ok"]:
      self.player_status.text = result["message"]
      return
    self.player_name.text = ""
    self.player_email.text = ""
    self.player_phone.text = ""
    self.player_city.text = ""
    self.player_state.text = ""
    self.player_handicap.text = ""
    self.app._load_players()
    self.app._load_event_data()
    self._show_player_add_mode(None)
    self.player_status.text = "Player added to the roster."

  @handle("import_players_button", "click")
  def import_players_button_click(self, **event_args):
    csv_file = self.player_csv_file.file
    if csv_file is None:
      self.player_status.text = "Choose a CSV file first."
      return

    self.import_players_button.enabled = False
    try:
      result = anvil.server.call("import_golfers_from_csv", csv_file)
    finally:
      self.import_players_button.enabled = True

    if not result["ok"]:
      self.player_status.text = result["message"]
      return

    self.app._load_players()
    self.app._load_event_data()
    self._show_player_add_mode(None)
    self.player_status.text = result["message"]

  @handle("player_rows", "x-save-player")
  def player_rows_save_player(self, golfer, name, email, phone, city, state, active, handicap, **event_args):
    result = anvil.server.call("update_golfer", golfer, name, email, phone, city, state, handicap)
    if not result["ok"]:
      self.player_status.text = result["message"]
      return

    if bool(active) != bool(golfer["active"]):
      status_result = anvil.server.call("set_golfer_active", golfer, active)
      if not status_result["ok"]:
        self.player_status.text = (
          "Player details were saved, but roster status was not updated: "
          + status_result["message"]
        )
        self.app._load_players()
        self.app._load_event_data()
        return

    self.player_status.text = "Player details and roster status updated."
    self.app._load_players()
    self.app._load_event_data()

  @handle("player_rows", "x-delete-player")
  def player_rows_delete_player(self, golfer, **event_args):
    name = golfer["name"]
    confirmed = confirm(
      f"Delete {name} from the roster and all tournaments? This permanently removes their scores, expense details, and tournament pairings. Shared pairing scores for other players in those pairings will also be removed.",
      title="Delete player",
    )
    if not confirmed:
      return

    result = anvil.server.call("delete_golfer", golfer)
    if not result["ok"]:
      self.player_status.text = result["message"]
      return
    self.app._reload_after_delete()
