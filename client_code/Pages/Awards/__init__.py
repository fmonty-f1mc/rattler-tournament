from ._anvil_designer import AwardsTemplate
from anvil import *
import anvil.server


class Awards(AwardsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    self.app = app
    self.history_scope.items = [("All years", "all"), ("Selected tournament", "selected")]
    self.history_scope.selected_value = "all"
    self._history = []

  def load(self, selected_award_id=None):
    previous_award = self.award_picker.selected_value
    previous_edit_award = self.edit_award_picker.selected_value
    edit_award_id = selected_award_id if selected_award_id is not None else (
      previous_edit_award.get_id() if previous_edit_award is not None else None
    )
    if selected_award_id is None and previous_award is not None:
      selected_award_id = previous_award.get_id()
    awards = anvil.server.call("list_awards")
    self.award_picker.items = [(award["name"], award) for award in awards]
    self.award_picker.selected_value = next(
      (award for award in awards if award.get_id() == selected_award_id), awards[0] if awards else None,
    )
    self.award_picker.enabled = bool(awards)
    self.edit_award_picker.items = [("New award", None)] + [(award["name"], award) for award in awards]
    self.edit_award_picker.selected_value = next(
      (award for award in awards if award.get_id() == edit_award_id), None,
    )
    self._set_award_editor()
    previous_player = self.player_picker.selected_value
    self.player_picker.items = [("Choose a player", None)] + [
      (golfer["name"] + (" (inactive)" if golfer["active"] is False else ""), golfer)
      for golfer in self.app.golfers
    ]
    self.player_picker.selected_value = next(
      (golfer for golfer in self.app.golfers if golfer == previous_player), None,
    )
    tournament = self.app.current_event
    self.assign_award_button.enabled = tournament is not None and bool(awards)
    self.award_status.text = "" if tournament is not None else "Create or select a tournament to record a winner."
    self._history = anvil.server.call("list_award_history")
    champion = next((
      record["golfer"]["name"] for record in self._history
      if record["tournament"] == tournament and record["award"]["is_champion"]
    ), None)
    self.champion_label.text = (
      f"{int(tournament['year'])} champion: {champion or 'Not recorded yet'}"
      if tournament is not None else "No tournament selected"
    )
    self._refresh_history()

  def _set_award_editor(self):
    award = self.edit_award_picker.selected_value
    self.edit_award_name.text = award["name"] if award is not None else ""
    self.save_award_button.text = "Create award" if award is None else "Save name"
    self.delete_award_button.visible = award is not None
    self.delete_award_button.enabled = award is not None
    self.edit_award_status.text = ""

  @handle("edit_award_picker", "change")
  def edit_award_picker_change(self, **event_args):
    self._set_award_editor()

  @handle("save_award_button", "click")
  def save_award_button_click(self, **event_args):
    award = self.edit_award_picker.selected_value
    if award is None:
      result = anvil.server.call("create_award", self.edit_award_name.text)
    else:
      result = anvil.server.call("rename_award", award, self.edit_award_name.text)
    if not result["ok"]:
      self.edit_award_status.text = result["message"]
      return
    self.load(result["award"].get_id())
    if award is not None:
      self.edit_award_status.text = "Award renamed throughout its history."
    elif result["restored"]:
      self.edit_award_status.text = "Award restored with its winner history."
    else:
      self.edit_award_status.text = "Award created. Choose a player to record a winner."

  @handle("delete_award_button", "click")
  def delete_award_button_click(self, **event_args):
    award = self.edit_award_picker.selected_value
    if award is None or not confirm(
      f"Delete ‘{award['name']}’ from available awards? Past winners will remain in history. Add this name again to restore the award.",
      title="Delete award",
    ):
      return
    result = anvil.server.call("delete_award", award)
    if not result["ok"]:
      self.edit_award_status.text = result["message"]
      return
    self.load()
    self.edit_award_status.text = "Award deleted from choices. Past winners are kept in history."

  def _refresh_history(self):
    records = self._history
    if self.history_scope.selected_value == "selected":
      records = [record for record in records if record["tournament"] == self.app.current_event]
    self.award_history.items = records
    self.empty_history.visible = not records

  @handle("assign_award_button", "click")
  def assign_award_button_click(self, **event_args):
    award = self.award_picker.selected_value
    player = self.player_picker.selected_value
    if self.app.current_event is None or award is None or player is None:
      self.award_status.text = "Select a tournament, award, and player."
      return
    self.assign_award_button.enabled = False
    try:
      result = anvil.server.call("assign_award", self.app.current_event, award, player)
      if not result["ok"]:
        self.award_status.text = result["message"]
        return
      self.load()
      self.award_status.text = "Champion updated." if result["replaced_champion"] else "Award recorded."
    finally:
      self.assign_award_button.enabled = self.app.current_event is not None and self.award_picker.selected_value is not None

  @handle("history_scope", "change")
  def history_scope_change(self, **event_args):
    self._refresh_history()

  @handle("award_history", "x-remove-award")
  def remove_record(self, record, **event_args):
    if not confirm(
      f"Remove {record['award']['name']} for {record['golfer']['name']} ({int(record['tournament']['year'])})?",
      title="Remove award record",
    ):
      return
    result = anvil.server.call("remove_award", record)
    self.load()
    self.award_status.text = "Award record removed." if result["ok"] else result["message"]
