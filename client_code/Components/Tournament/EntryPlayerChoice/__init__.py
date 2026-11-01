from ._anvil_designer import EntryPlayerChoiceTemplate
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class EntryPlayerChoice(EntryPlayerChoiceTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
