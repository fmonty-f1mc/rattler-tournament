from ._anvil_designer import PlayerHistoryRowTemplate


class PlayerHistoryRow(PlayerHistoryRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def rattlercap_text(self):
    entry = self.item["entry"]
    if entry is None:
      return "Not recorded"
    if entry["is_player"] is False:
      return "Not applicable"
    cap = entry["handicap"]
    return "Not recorded" if cap is None else f"{cap:g}"

  def score_text(self, field):
    entry = self.item["entry"]
    if entry is None:
      return "Not recorded"
    if entry["is_player"] is False:
      return "Not applicable"
    value = entry["gross_18"] if field == "gross" else self.item[field]
    return "Not recorded" if value is None else f"{value:g}"
