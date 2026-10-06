from ._anvil_designer import PairingRowTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class PairingRow(PairingRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    best_ball_values = []
    for hole in range(1, 10):
      value = self.item[f"hole_{hole}"]
      getattr(self, f"hole_{hole}").text = self._display_score(value)
      if value is not None and value > 0:
        best_ball_values.append(value)
    if len(best_ball_values) == 9:
      self.best_ball_label.text = f"Best-ball total · {sum(best_ball_values)}"
    else:
      self.best_ball_label.text = f"Best ball · {len(best_ball_values)}/9 holes scored"

  @staticmethod
  def _display_score(value):
    return "" if value is None or value <= 0 else str(value)

  @handle("save_button", "click")
  def save_button_click(self, **event_args):
    scores = [getattr(self, f"hole_{hole}").text for hole in range(1, 10)]
    self.parent.raise_event(
      "x-save-rattler-card",
      pairing=self.item,
      scores=scores,
    )
