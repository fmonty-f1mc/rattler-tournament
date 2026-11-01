from ._anvil_designer import NewsEditorTemplate
from anvil import *
import anvil.server


class NewsEditor(NewsEditorTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self.news_status.text = ""

  def _load_news_posts(self, selected_post_id=None):
    tournament = self.app.current_event
    posts = anvil.server.call("list_committee_news_posts", tournament) if tournament else []
    self.news_post_picker.items = [("New post", None)] + [
      (
        ("Unassigned · " if post["tournament"] is None else "") + post["title"],
        post,
      )
      for post in posts
    ]
    selected_post = next(
      (post for post in posts if post.get_id() == selected_post_id),
      None,
    )
    self.news_post_picker.selected_value = selected_post
    self._set_news_editor_post(selected_post)
    self.save_news_post_button.enabled = tournament is not None
    self.news_status.text = (
      "Create or select a tournament before managing news."
      if tournament is None else ""
    )

  def _set_news_editor_post(self, post):
    self.current_news_post = post
    self.news_post_title.text = post["title"] if post else ""
    self.news_post_body.text = post["body"] if post else ""
    self.delete_news_post_button.enabled = (
      post is not None and self.app.current_event is not None
    )

  @handle("news_post_picker", "change")
  def news_post_picker_change(self, **event_args):
    self._set_news_editor_post(self.news_post_picker.selected_value)
    self.news_status.text = ""

  @handle("save_news_post_button", "click")
  def save_news_post_button_click(self, **event_args):
    result = anvil.server.call(
      "save_news_post",
      self.current_news_post,
      self.app.current_event,
      self.news_post_title.text,
      self.news_post_body.text,
    )
    if not result["ok"]:
      self.news_status.text = result["message"]
      return
    self._load_news_posts(result["post"].get_id())
    self.news_status.text = "News post saved and published."

  @handle("delete_news_post_button", "click")
  def delete_news_post_button_click(self, **event_args):
    post = self.current_news_post
    if post is None:
      return
    if not confirm(f"Delete ‘{post['title']}’ from public News?", title="Delete news post"):
      return
    result = anvil.server.call("delete_news_post", post, self.app.current_event)
    if not result["ok"]:
      self.news_status.text = result["message"]
      return
    self.app._reload_after_delete()
