from ._anvil_designer import ImportedYearRowTemplate
from anvil import *


class ImportedYearRow(ImportedYearRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  @handle('view_source_button', 'click')
  def view_source_click(self, **event_args):
    self.parent.raise_event('x-view-source', record=self.item)

  @handle('open_tournament_button', 'click')
  def open_tournament_click(self, **event_args):
    self.parent.raise_event('x-open-tournament', tournament=self.item['tournament'])
