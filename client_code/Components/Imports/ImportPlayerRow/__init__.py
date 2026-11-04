from ._anvil_designer import ImportPlayerRowTemplate


class ImportPlayerRow(ImportPlayerRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def capture(self):
    if self.item['editable']:
      self.item['name'] = self.import_name.text or ''

  def set_busy(self, busy):
    self.import_name.enabled = not busy and self.item['editable']
