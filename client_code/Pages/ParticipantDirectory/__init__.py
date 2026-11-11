from ._anvil_designer import ParticipantDirectoryTemplate
from anvil import *
import anvil.server
import anvil.media
from ...Components.Participants.DirectoryEditRow import DirectoryEditRow


class ParticipantDirectory(ParticipantDirectoryTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self._editing_directory = False
    self._directory_rows = []
    self._directory_originals = {}
    self._directory_revisions = {}
    self._preview_file = None
    self._preview_count = 0
    self.official_handicap_filter.items = [
      ("All handicap statuses", "all"),
      ("Official handicap", "official"),
      ("Not official handicap", "not_official"),
    ]
    self.official_handicap_filter.selected_value = "all"
    self.player_status.text = ""
    self._show_player_add_mode(None)

  def _refresh_player_rows(self):
    self._commit_directory_cells()
    current_year_ids = None
    if self.current_year_participants_filter.checked:
      self.current_year_participants_filter.enabled = False
      try:
        result = anvil.server.call("list_current_year_participants")
        current_year_ids = {golfer.get_id() for golfer in result["participants"]}
        self.current_year_participants_filter.text = f"Current year participants ({result['year']})"
      finally:
        self.current_year_participants_filter.enabled = True
    query = (self.player_search.text or "").strip().lower()
    email_unlisted = self.email_unlisted_filter.checked
    phone_unlisted = self.phone_unlisted_filter.checked
    handicap_unlisted = self.handicap_unlisted_filter.checked
    official_status = self.official_handicap_filter.selected_value or "all"
    matches = []

    roster = self._directory_rows if self._editing_directory else self.app.golfers
    for golfer in roster:
      if current_year_ids is not None and golfer.get_id() not in current_year_ids:
        continue
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
      if handicap_unlisted and golfer["handicap"] is not None:
        continue
      if official_status == "official" and not golfer["handicap_official"]:
        continue
      if official_status == "not_official" and golfer["handicap_official"]:
        continue
      matches.append(golfer)

    if self._editing_directory:
      self.directory_edit_rows.items = matches
    else:
      self.player_rows.items = matches
    self.player_filter_status.text = (
      f"Showing {len(matches)} of {len(roster)} participants"
    )
    self.no_player_matches.visible = not matches
    self.no_player_matches.text = (
      "No participants in the roster yet."
      if not roster else "No participants match these filters."
    )

  def _commit_directory_cells(self):
    if self._editing_directory:
      for row_form in self.directory_edit_rows.get_components():
        if isinstance(row_form, DirectoryEditRow):
          row_form.commit()

  def _directory_values(self, row):
    return {field: (bool(row[field]) if field in ("active", "handicap_official") else row[field] if field == "handicap"
                    else row[field] or "")
            for field in ("name", "email", "phone", "city", "state", "handicap", "handicap_official", "active")}

  def _directory_dirty_rows(self):
    return [row for row in self._directory_rows
            if self._directory_values(row) != self._directory_originals[row.get_id()]]

  @handle("directory_edit_rows", "x-directory-change")
  def directory_cell_change(self, **event_args):
    count = len(self._directory_dirty_rows())
    self.directory_draft_status.text = f"{count} participant(s) with unsaved changes"

  def _set_directory_busy(self, busy):
    for name in ("edit_directory_button", "export_directory_button", "open_directory_import_button",
                 "save_directory_button", "cancel_directory_button", "player_search",
                 "email_unlisted_filter", "phone_unlisted_filter", "directory_csv_file",
                 "handicap_unlisted_filter", "official_handicap_filter",
                 "current_year_participants_filter",
                 "preview_directory_button", "close_directory_import_button",
                 "open_individual_player_add_button", "open_bulk_player_add_button",
                 "create_player_button", "import_players_button"):
      getattr(self, name).enabled = not busy
    self.apply_directory_import_button.enabled = not busy and self._preview_count > 0
    for row_form in self.directory_edit_rows.get_components():
      if isinstance(row_form, DirectoryEditRow):
        row_form.set_enabled(not busy)

  def _finish_directory_editing(self):
    # Buffers provide Cancel without writing to the database.
    for row in self._directory_rows:
      row.reset()
      row.buffer_changes(False)
    self._directory_rows = []
    self._directory_originals = {}
    self._directory_revisions = {}
    self.directory_edit_rows.items = []
    self._editing_directory = False
    self.directory_edit_actions.visible = False
    self.directory_spreadsheet.visible = False
    self.player_rows.visible = True
    self.edit_directory_button.visible = True
    self.export_directory_button.visible = True
    self.open_directory_import_button.visible = True
    self._show_player_add_mode(None)

  @handle("edit_directory_button", "click")
  def edit_directory_button_click(self, **event_args):
    self._set_directory_busy(True)
    try:
      result = anvil.server.call("load_directory_for_editing")
    finally:
      self._set_directory_busy(False)
    self._directory_rows = result["rows"]
    self._directory_revisions = result["revisions"]
    self._directory_originals = {row.get_id(): self._directory_values(row) for row in self._directory_rows}
    for row in self._directory_rows:
      row.buffer_changes(True)
    self._editing_directory = True
    self._clear_directory_preview()
    self.directory_import_panel.visible = False
    self._show_player_add_mode(None)
    self.player_add_options.visible = False
    self.directory_edit_actions.visible = True
    self.directory_spreadsheet.visible = True
    self.player_rows.visible = False
    self.edit_directory_button.visible = False
    self.export_directory_button.visible = False
    self.open_directory_import_button.visible = False
    self.directory_draft_status.text = "Edit any cell, then save all changes."
    self._refresh_player_rows()

  @handle("cancel_directory_button", "click")
  def cancel_directory_button_click(self, **event_args):
    self._commit_directory_cells()
    if self._directory_dirty_rows() and not confirm("Discard all unsaved directory changes?", title="Cancel spreadsheet edits"):
      return
    self._finish_directory_editing()
    # The buffers were reset above; Cancel only needs to redraw the cached roster.
    self._refresh_player_rows()
    self.player_status.text = "Spreadsheet edits discarded."

  @handle("save_directory_button", "click")
  def save_directory_button_click(self, **event_args):
    self._commit_directory_cells()
    updates = [{"participant_id": row.get_id(), "revision": self._directory_revisions[row.get_id()],
                "values": self._directory_values(row)} for row in self._directory_dirty_rows()]
    self._set_directory_busy(True)
    try:
      result = anvil.server.call("save_directory_updates", updates)
      if not result["ok"]:
        self.player_status.text = result["message"]
        return
      self._finish_directory_editing()
      self.app._load_players()
      self.app._load_event_data()
      self.player_status.text = f"Saved changes to {result['updated_count']} participant(s)."
    finally:
      self._set_directory_busy(False)

  @handle("export_directory_button", "click")
  def export_directory_button_click(self, **event_args):
    self._set_directory_busy(True)
    try:
      anvil.media.download(anvil.server.call("export_participant_directory"))
      self.player_status.text = "Exported the full directory, including participants hidden by filters."
    finally:
      self._set_directory_busy(False)

  def _clear_directory_preview(self):
    self._preview_file = None
    self._preview_count = 0
    self.directory_preview_rows.items = []
    self.directory_preview_panel.visible = False
    self.directory_import_status.text = ""
    self.apply_directory_import_button.enabled = False

  @handle("open_directory_import_button", "click")
  def open_directory_import_button_click(self, **event_args):
    self._show_player_add_mode(None)
    self.player_add_options.visible = False
    self._clear_directory_preview()
    self.directory_import_panel.visible = True

  @handle("close_directory_import_button", "click")
  def close_directory_import_button_click(self, **event_args):
    self._clear_directory_preview()
    self.directory_import_panel.visible = False
    self._show_player_add_mode(None)

  @handle("directory_csv_file", "change")
  def directory_csv_file_change(self, **event_args):
    self._clear_directory_preview()

  @handle("preview_directory_button", "click")
  def preview_directory_button_click(self, **event_args):
    self._clear_directory_preview()
    csv_file = self.directory_csv_file.file
    self._set_directory_busy(True)
    try:
      result = anvil.server.call("preview_directory_csv", csv_file)
      if not result["ok"]:
        self.directory_import_status.text = result["message"]
        return
      self._preview_file = csv_file
      self._preview_count = result["updated_count"]
      self.directory_preview_rows.items = result["changes"]
      self.directory_preview_panel.visible = self._preview_count > 0
      self.directory_import_status.text = (
        f"{self._preview_count} participant(s), {len(result['changes'])} cell change(s). Review below before applying."
        if self._preview_count else "No changes found."
      )
    finally:
      self._set_directory_busy(False)

  @handle("apply_directory_import_button", "click")
  def apply_directory_import_button_click(self, **event_args):
    if self._preview_file is None or not self._preview_count:
      return
    self._set_directory_busy(True)
    try:
      result = anvil.server.call("apply_directory_csv", self._preview_file)
      self._clear_directory_preview()
      if not result["ok"]:
        self.directory_import_status.text = result["message"]
        return
      self.app._load_players()
      self.app._load_event_data()
      self.directory_import_status.text = f"Updated {result['updated_count']} participant(s)."
    finally:
      self._set_directory_busy(False)

  @handle("player_search", "change")
  def player_search_change(self, **event_args):
    self._refresh_player_rows()

  @handle("email_unlisted_filter", "change")
  def email_unlisted_filter_change(self, **event_args):
    self._refresh_player_rows()

  @handle("phone_unlisted_filter", "change")
  def phone_unlisted_filter_change(self, **event_args):
    self._refresh_player_rows()

  @handle("handicap_unlisted_filter", "change")
  @handle("official_handicap_filter", "change")
  @handle("current_year_participants_filter", "change")
  def handicap_filters_change(self, **event_args):
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
      self.player_handicap_official.checked,
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
    self.player_handicap_official.checked = False
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
  def player_rows_save_player(self, golfer, name, email, phone, city, state, active, handicap, handicap_official, **event_args):
    result = anvil.server.call("update_golfer", golfer, name, email, phone, city, state, handicap, handicap_official)
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
