from ._anvil_designer import ImportYearRowTemplate
from anvil import *


class ImportYearRow(ImportYearRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def capture(self):
    self.item['selected'] = self.select_year.checked
    self.item['course'] = self.course_name.text or ''

  def set_busy(self, busy):
    self.select_year.enabled = not busy and not self.item['errors']
    self.course_name.enabled = not busy
    self.review_button.enabled = not busy

  @handle('select_year', 'change')
  @handle('course_name', 'lost_focus')
  def selection_changed(self, **event_args):
    self.capture()
    self.parent.raise_event('x-selection-changed')

  @handle('review_button', 'click')
  def review_click(self, **event_args):
    self.capture()
    self.parent.raise_event('x-review-year', document=self.item)
