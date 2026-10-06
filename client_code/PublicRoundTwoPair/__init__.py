from ._anvil_designer import PublicRoundTwoPairTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class PublicRoundTwoPair(PublicRoundTwoPairTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
