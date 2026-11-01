from ._anvil_designer import BaseLayoutTemplate
from anvil import *
from anvil.js.window import window
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files


class BaseLayout(BaseLayoutTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def _set_navigation_open(self, is_open):
    self._navigation_open = is_open
    self.classes["navigation-open"] = is_open
    self.dom_nodes["navigation_toggle"].setAttribute(
      "aria-expanded", "true" if is_open else "false"
    )

  def toggle_navigation(self, event):
    self._set_navigation_open(not getattr(self, "_navigation_open", False))

  def _close_mobile_navigation(self):
    if window.matchMedia("(max-width: 900px)").matches:
      self._set_navigation_open(False)
      self.dom_nodes["navigation_toggle"].focus()

  def navigation_click(self, event):
    # Page buttons close the panel; tournament dropdown interaction keeps it open.
    if event.target.closest("button") is not None:
      self._close_mobile_navigation()

  def navigation_keydown(self, event):
    if event.key == "Escape" and getattr(self, "_navigation_open", False):
      self._close_mobile_navigation()
