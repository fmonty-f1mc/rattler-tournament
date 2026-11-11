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
    self.email_preview.visible = False
    self.email_addresses_preview.visible = False
    self._load_email_filters(None, [])

  def _load_email_filters(self, tournament, entries):
    recipient_options = [
      ("Everyone", "all"), ("Players", "players"), ("Non-players", "non_players"),
      ("Test — CC only", "test"),
    ]
    if tournament is None:
      self.email_no_handicap.checked = False
      self.email_addresses_preview.visible = False
      self._email_filter_tournament_id = None
      self._email_has_players = False
      self.email_recipient_type.items = recipient_options
      self.email_recipient_type.selected_value = "all"
      self.email_recipient_type.enabled = False
      self.email_division_filter.items = [("All divisions", "all")]
      self.email_division_filter.selected_value = "all"
      self.email_division_filter.enabled = False
      self._update_email_recipient_controls()
      return

    tournament_id = tournament.get_id()
    if self._email_filter_tournament_id != tournament_id:
      self.email_preview.visible = False
      self.email_addresses_preview.visible = False
      self.email_no_handicap.checked = False
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
    self.email_recipient_type.enabled = True
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
    if self.email_recipient_type.selected_value in ("non_players", "test"):
      self.email_division_filter.selected_value = "all"
    self.email_division_filter.enabled = (
      self.app.current_event is not None
      and self._email_has_players
      and self.email_recipient_type.selected_value not in ("non_players", "test")
    )
    self._update_email_recipient_controls()

  def _update_email_recipient_controls(self):
    test_mode = self.email_recipient_type.selected_value == "test"
    self.email_test_hint.visible = test_mode
    if test_mode:
      self.email_no_handicap.checked = False
    self.email_no_handicap.enabled = self.app.current_event is not None and not test_mode
    self.preview_emails_button.enabled = self.app.current_event is not None
    self.export_email_list_button.enabled = self.app.current_event is not None and not test_mode
    self.send_tournament_email_button.text = (
      "Send test email to CC" if test_mode else "Send email to participants"
    )

  @handle("email_recipient_type", "change")
  def email_recipient_type_change(self, **event_args):
    self.email_addresses_preview.visible = False
    self._update_email_division_filter_state()

  @handle("email_division_filter", "change")
  @handle("email_no_handicap", "change")
  @handle("email_cc", "change")
  def email_recipient_filters_change(self, **event_args):
    self.email_addresses_preview.visible = False

  @handle("preview_emails_button", "click")
  def preview_emails_button_click(self, **event_args):
    if self.app.current_event is None:
      self.email_status.text = "Create or select a tournament first."
      return
    self.email_addresses_preview.visible = False
    self.preview_emails_button.enabled = False
    try:
      result = anvil.server.call(
        "get_tournament_email_summary", self.app.current_event,
        self.email_recipient_type.selected_value or "all",
        self.email_division_filter.selected_value or "all",
        self.email_cc.text or "", self.email_no_handicap.checked,
      )
      if not result["ok"]:
        self.email_status.text = result["message"]
        return
      cc_keys = {address.lower() for address in result["cc_addresses"]}
      bcc = [address for address in result["recipient_addresses"] if address.lower() not in cc_keys]
      self.email_addresses_preview.text = (
        f"Matching participant email addresses: {result['recipient_count']}\n"
        + "BCC: " + ("; ".join(bcc) or "None")
        + "\nCC: " + ("; ".join(result["cc_addresses"]) or "None")
        + f"\nSkipped: {result['missing_count']} missing; {result['invalid_count']} invalid."
        + ("\nTest mode: only CC addresses will receive the email." if result["test_mode"] else "")
      )
      self.email_addresses_preview.visible = True
      self.email_status.text = "Recipient preview ready. No email has been sent."
    finally:
      self._update_email_recipient_controls()

  @handle("export_email_list_button", "click")
  def export_email_list_button_click(self, **event_args):
    if self.app.current_event is None:
      self.email_status.text = "Create or select a tournament first."
      return
    if self.email_recipient_type.selected_value == "test":
      self.email_status.text = "Choose a participant list to export email addresses."
      return
    self.export_email_list_button.enabled = False
    try:
      result = anvil.server.call(
        "export_tournament_email_list", self.app.current_event,
        self.email_recipient_type.selected_value or "all",
        self.email_division_filter.selected_value or "all",
        self.email_no_handicap.checked,
      )
      if not result["ok"]:
        self.email_status.text = result["message"]
        return
      anvil.media.download(result["file"])
      skipped = result["missing_count"] + result["invalid_count"]
      self.email_status.text = f"Exported {result['recipient_count']} unique email addresses. Skipped {skipped} participant(s) with missing or invalid email addresses."
    finally:
      self._update_email_recipient_controls()

  @handle("send_tournament_email_button", "click")
  def send_tournament_email_button_click(self, **event_args):
    if self.app.current_event is None:
      self.email_status.text = "Create or select a tournament first."
      return

    subject = (self.email_subject.text or "").strip()
    body = (self.email_body.text or "").strip()
    cc = self.email_cc.text or ""
    include_sections = self._selected_email_sections()
    if not subject:
      self.email_status.text = "Enter an email subject."
      return
    if not body and not include_sections:
      self.email_status.text = "Enter a message or select tournament information to include."
      return

    self.send_tournament_email_button.enabled = False
    recipient_type = self.email_recipient_type.selected_value or "all"
    division_filter = self.email_division_filter.selected_value or "all"
    try:
      preview = self._load_email_preview(body, include_sections)
      if not preview["ok"]:
        self.email_status.text = preview["message"]
        return
      summary = anvil.server.call(
        "get_tournament_email_summary",
        self.app.current_event,
        recipient_type,
        division_filter,
        cc,
        self.email_no_handicap.checked,
      )
    finally:
      self.send_tournament_email_button.enabled = True

    if not summary["ok"]:
      self.email_status.text = summary["message"]
      return
    recipient_count = summary["recipient_count"]
    test_mode = summary["test_mode"]
    if not recipient_count and not test_mode:
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
    cc_message = (
      " CC (visible to all recipients): " + ", ".join(summary["cc_addresses"]) + "."
      if summary["cc_addresses"] else ""
    )
    section_message = (
      " Includes: " + ", ".join(preview["section_titles"]) + "."
      if preview["section_titles"] else ""
    )
    warning_message = " " + " ".join(preview["warnings"]) if preview["warnings"] else ""
    confirmation_message = (
      "Send a test email only to these CC addresses: "
      + ", ".join(summary["cc_addresses"]) + "? "
      + "Tournament participant lists will not receive this email."
      if test_mode else
      f"Send this message to {recipient_count} unique email addresses for "
      f"{self.app.current_event['year']} · {self.app.current_event['course']}? "
      f"Participant addresses will be BCCed unless also listed in CC.{cc_message}"
    )
    confirmed = confirm(
      confirmation_message + section_message + warning_message + skipped_message,
      title="Send test email" if test_mode else "Email tournament participants",
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
        cc,
        include_sections,
        self.email_no_handicap.checked,
      )
    finally:
      self.send_tournament_email_button.enabled = True

    self.email_status.text = result["message"]

  def _selected_email_sections(self):
    return [
      key for key, checkbox in (
        ("details", self.include_details),
        ("round_one", self.include_round_one),
        ("round_two", self.include_round_two),
        ("standings", self.include_standings),
        ("division_standings", self.include_division_standings),
        ("awards", self.include_awards),
      ) if checkbox.checked
    ]

  def _load_email_preview(self, body, include_sections):
    self.email_preview.visible = False
    result = anvil.server.call(
      "preview_tournament_email", self.app.current_event, body, include_sections,
    )
    if result["ok"]:
      self.email_preview.text = result["body"]
      self.email_preview.visible = True
    return result

  @handle("preview_email_button", "click")
  def preview_email_button_click(self, **event_args):
    if self.app.current_event is None:
      self.email_status.text = "Create or select a tournament first."
      return
    self.preview_email_button.enabled = False
    try:
      result = self._load_email_preview(
        (self.email_body.text or "").strip(), self._selected_email_sections(),
      )
      if result["ok"]:
        self.email_status.text = " ".join(result["warnings"]) or "Preview ready."
      else:
        self.email_status.text = result["message"]
    finally:
      self.preview_email_button.enabled = True

  @handle("email_body", "change")
  @handle("include_details", "change")
  @handle("include_round_one", "change")
  @handle("include_round_two", "change")
  @handle("include_standings", "change")
  @handle("include_division_standings", "change")
  @handle("include_awards", "change")
  def email_content_change(self, **event_args):
    self.email_preview.visible = False
