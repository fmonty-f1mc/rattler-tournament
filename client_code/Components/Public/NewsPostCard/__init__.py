from ._anvil_designer import NewsPostCardTemplate
from anvil import *


class NewsPostCard(NewsPostCardTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
