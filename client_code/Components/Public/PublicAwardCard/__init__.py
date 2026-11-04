from ._anvil_designer import PublicAwardCardTemplate
from anvil import *


class PublicAwardCard(PublicAwardCardTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
