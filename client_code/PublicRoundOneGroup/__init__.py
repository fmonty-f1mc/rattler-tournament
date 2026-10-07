from ._anvil_designer import PublicRoundOneGroupTemplate
from anvil import *


class PublicRoundOneGroup(PublicRoundOneGroupTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
