from ._anvil_designer import EmailParticipantsTemplate
from anvil import *
import anvil.server
import anvil.media


class EmailParticipants(EmailParticipantsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self._email_filter_tournament_id = None
    self._email_has_players = False
    self._email_default_subject = None
    self.email_status.text = ""

  def clear(self):
    self._load_email_filters(None, [])

  def _load_email_filters(self, tournament, entries):
    recipient_options = [
      ("Everyone", "all"), ("Players", "players"), ("Non-players", "non_players")
    ]
    if tournament is None:
      self._email_filter_tournament_id = None
      self._email_has_players = False
      self.email_recipient_type.items = recipient_options
      self.email_recipient_type.selected_value = "all"
      self.email_recipient_type.enabled = False
      self.email_division_filter.items = [("All divisions", "all")]
      self.email_division_filter.selected_value = "all"
      self.email_division_filter.enabled = False
      return

    tournament_id = tournament.get_id()
    if self._email_filter_tournament_id != tournament_id:
      self._email_filter_tournament_id = tournament_id
      self.email_recipient_type.selected_value = "all"
      self.email_division_filter.selected_value = "all"

    division_options = [
      ("All divisions", "all"), ("Players without a division", "unassigned")
    ] + [
      (division, "division:" + division)
      for division in sorted(self.app.division_options, key=lambda value: value.lower())
    ]
    selected_recipient = self.email_recipient_type.selected_value or "all"
    selected_division = self.email_division_filter.selected_value or "all"
    self.email_recipient_type.items = recipient_options
    self.email_recipient_type.selected_value = next(
      (value for _, value in recipient_options if value == selected_recipient), "all"
    )
    self.email_division_filter.items = division_options
    self.email_division_filter.selected_value = next(
      (value for _, value in division_options if value == selected_division), "all"
    )
    self._email_has_players = any(
      entry["is_player"] is not False for entry in entries
    )
    self.email_recipient_type.enabled = bool(entries)
    self._update_email_division_filter_state()

  def _set_email_subject_default(self, tournament):
    year = tournament["year"]
    year_label = str(int(year)) if year is not None and int(year) == year else str(year)
    default_subject = f"[RattlerMail {year_label}]"
    current_subject = (self.email_subject.text or "").strip()
    if not current_subject or current_subject == self._email_default_subject:
      self.email_subject.text = default_subject
    self._email_default_subject = default_subject

  def _update_email_division_filter_state(self):
    if self.email_recipient_type.selected_value == "non_players":
      self.email_division_filter.selected_value = "all"
    self.email_division_filter.enabled = (
      self.app.current_event is not None
      and self._email_has_players
      and self.email_recipient_type.selected_value != "non_players"
    )

  @handle("email_recipient_type", "change")
  def email_recipient_type_change(self, **event_args):
    self._update_email_division_filter_state()

  @handle("export_email_list_button", "click")
  def export_email_list_button_click(self, **event_args):
    if self.app.current_event is None:
      self.email_status.text = "Create or select a tournament first."
      return
    self.export_email_list_button.enabled = False
    try:
      result = anvil.server.call(
        "export_tournament_email_list", self.app.current_event,
        self.email_recipient_type.selected_value or "all",
        self.email_division_filter.selected_value or "all",
      )
      if not result["ok"]:
        self.email_status.text = result["message"]
        return
      anvil.media.download(result["file"])
      skipped = result["missing_count"] + result["invalid_count"]
      self.email_status.text = f"Exported {result['recipient_count']} unique email addresses. Skipped {skipped} participant(s) with missing or invalid email addresses."
    finally:
      self.export_email_list_button.enabled = True

  @handle("send_tournament_email_button", "click")
  def send_tournament_email_button_click(self, **event_args):
    if self.app.current_event is None:
      self.email_status.text = "Create or select a tournament first."
      return

    subject = (self.email_subject.text or "").strip()
    body = (self.email_body.text or "").strip()
    if not subject:
      self.email_status.text = "Enter an email subject."
      return
    if not body:
      self.email_status.text = "Enter a message."
      return

    self.send_tournament_email_button.enabled = False
    recipient_type = self.email_recipient_type.selected_value or "all"
    division_filter = self.email_division_filter.selected_value or "all"
    try:
      summary = anvil.server.call(
        "get_tournament_email_summary",
        self.app.current_event,
        recipient_type,
        division_filter,
      )
    finally:
      self.send_tournament_email_button.enabled = True

    if not summary["ok"]:
      self.email_status.text = summary["message"]
      return
    recipient_count = summary["recipient_count"]
    if not recipient_count:
      self.email_status.text = "No matching participants have a usable email address."
      return

    skipped_details = []
    if summary["missing_count"]:
      skipped_details.append(f"{summary['missing_count']} without an email address")
    if summary["invalid_count"]:
      skipped_details.append(f"{summary['invalid_count']} with an invalid email address")
    skipped_message = (
      " Participants with " + " and ".join(skipped_details) + " will be skipped."
      if skipped_details else ""
    )
    confirmed = confirm(
      f"Send this message to {recipient_count} unique email addresses for "
      f"{self.app.current_event['year']} · {self.app.current_event['course']}? "
      f"Recipients will be BCCed.{skipped_message}",
      title="Email tournament participants",
    )
    if not confirmed:
      return

    self.email_status.text = "Sending email…"
    self.send_tournament_email_button.enabled = False
    try:
      result = anvil.server.call(
        "send_tournament_email",
        self.app.current_event,
        subject,
        body,
        recipient_type,
        division_filter,
      )
    finally:
      self.send_tournament_email_button.enabled = True

    self.email_status.text = result["message"]
