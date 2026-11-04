from ._anvil_designer import HistoricalScoreRowTemplate


class HistoricalScoreRow(HistoricalScoreRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
