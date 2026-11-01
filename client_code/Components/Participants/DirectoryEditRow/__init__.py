from ._anvil_designer import DirectoryEditRowTemplate
from anvil import *


class DirectoryEditRow(DirectoryEditRowTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.active_picker.items = [("Active", True), ("Inactive", False)]
    self.refresh_data_bindings()
    self.active_picker.selected_value = bool(self.item["active"])

  def commit(self):
    # Include the currently focused input when Save or a filter is clicked.
    for field in ("name", "email", "phone", "city", "state", "handicap"):
      value = getattr(self, field + "_box").text
      if field == "handicap" and (value is None or str(value).strip() == ""):
        value = None
      elif field == "handicap":
        try:
          value = float(value)
        except (TypeError, ValueError):
          pass  # Keep invalid input staged so the server can explain the error.
      if self.item[field] != value:
        self.item[field] = value
    if self.item["active"] != self.active_picker.selected_value:
      self.item["active"] = self.active_picker.selected_value

  def set_enabled(self, enabled):
    for field in ("name", "email", "phone", "city", "state", "handicap"):
      getattr(self, field + "_box").enabled = enabled
    self.active_picker.enabled = enabled

  @handle("name_box", "change")
  @handle("email_box", "change")
  @handle("phone_box", "change")
  @handle("city_box", "change")
  @handle("state_box", "change")
  @handle("handicap_box", "change")
  @handle("active_picker", "change")
  def cell_change(self, **event_args):
    self.commit()
    self.parent.raise_event("x-directory-change")
