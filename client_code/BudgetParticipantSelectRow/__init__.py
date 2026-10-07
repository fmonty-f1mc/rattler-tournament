from ._anvil_designer import BudgetParticipantSelectRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class BudgetParticipantSelectRow(BudgetParticipantSelectRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.participant_checkbox.checked = self.item["selected"]
    self.participant_checkbox.text = self.item["name"]
    self.participant_label.text = self.item["participant_label"]

  @handle("participant_checkbox", "change")
  def participant_checkbox_change(self, **event_args):
    self.item["selected"] = self.participant_checkbox.checked
    self.parent.raise_event("x-budget-target-selection-changed")
