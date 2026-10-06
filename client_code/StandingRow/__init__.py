from ._anvil_designer import StandingRowTemplate
from anvil import *


class StandingRow(StandingRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
