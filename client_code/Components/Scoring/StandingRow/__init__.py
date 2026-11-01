from ._anvil_designer import StandingRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class StandingRow(StandingRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
