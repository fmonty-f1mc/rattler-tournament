from ._anvil_designer import DirectoryImportChangeTemplate


class DirectoryImportChange(DirectoryImportChangeTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
