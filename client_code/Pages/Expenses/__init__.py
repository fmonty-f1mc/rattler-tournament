from ._anvil_designer import ExpensesTemplate
from anvil import *
import anvil.server


class Expenses(ExpensesTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    """Attach shared tournament context; keep edits local to this page."""
    self.app = app
    self._budget_target_items: list = []
    self._budget_cost_items = []
    self._budget_selected_entry_ids = set()
    self._budget_selection_tournament_id = None
    self.budget_status.text = ""

  def clear(self):
    self.budget_rows.items = []
    self._budget_cost_items = []
    self.budget_category_rows.items = []
    self.budget_target_rows.items = []
    self.budget_bulk_category_picker.items = []
    self.budget_bulk_category_picker.selected_value = None
    self.budget_target_filter.items = [("Everyone", "all")]
    self.budget_target_filter.selected_value = "all"
    self.budget_division_filter.items = [("All divisions", "all")]
    self.budget_division_filter.selected_value = "all"
    self.budget_target_search.text = ""
    self.budget_cost_type_filter.items = [("Everyone", "all")]
    self.budget_cost_type_filter.selected_value = "all"
    self.budget_cost_division_filter.items = [("All divisions", "all")]
    self.budget_cost_division_filter.selected_value = "all"
    self.budget_cost_search.text = ""
    self.budget_cost_match_status.text = "0 participants"
    self.budget_payment_selection_status.text = "0 participants selected."
    self._budget_target_items: list = []
    self._budget_selected_entry_ids = set()
    self._budget_selection_tournament_id = None
    self.budget_target_selection_status.text = "0 participants selected."
    self.new_budget_category_name.text = ""
    self.budget_total.text = "$0.00"
    self.budget_paid.text = "$0.00"
    self.budget_balance.text = "$0.00"
    self.budget_participants.text = "0 participants"

  def load(self, tournament):
    summary = anvil.server.call("get_budget_summary", tournament)
    self.budget_category_rows.items = summary["categories"]
    self._load_budget_cost_items(summary["rows"])
    selected_category_id = (
      self.budget_bulk_category_picker.selected_value.get_id()
      if self.budget_bulk_category_picker.selected_value is not None
      else None
    )
    category_options = [
      (category["name"], category["category"])
      for category in summary["categories"]
      if category["category"] is not None
    ]
    self.budget_bulk_category_picker.items = category_options
    self.budget_bulk_category_picker.selected_value = next(
      (
        category
        for _, category in category_options
        if category.get_id() == selected_category_id
      ),
      category_options[0][1] if category_options else None,
    )
    self._load_budget_target_items(summary["rows"], tournament)
    self.budget_total.text = self._money(summary["total"])
    self.budget_paid.text = self._money(summary["paid"])
    self.budget_balance.text = self._money(summary["balance"])
    count = summary["participants"]
    self.budget_participants.text = f"{count} participant" + ("s" if count != 1 else "")

  def _update_budget_navigation(self):
    for tab_name, button in (
      ("categories", self.app.budget_categories_tab_button),
      ("assign", self.app.budget_assignments_tab_button),
      ("payments", self.app.budget_payments_tab_button),
    ):
      button.role = (
        "tournament-subtab-active"
        if self.app._active_view == "budget" and getattr(self, "_active_budget_tab", "categories") == tab_name
        else "tournament-subtab"
      )

  def _show_budget_tab(self, name):
    self._active_budget_tab = name
    for tab_name, panel, button in (
      ("categories", self.budget_categories_tab, self.app.budget_categories_tab_button),
      ("assign", self.budget_assignments_tab, self.app.budget_assignments_tab_button),
      ("payments", self.budget_payments_tab, self.app.budget_payments_tab_button),
    ):
      panel.visible = name == tab_name
    self._update_budget_navigation()

  def _load_budget_cost_items(self, rows):
    self._budget_cost_items = []
    divisions = set()
    for row in rows:
      entry = row["entry"]
      is_player = entry["is_player"] is not False
      division = (entry["division"] or "").strip() if is_player else ""
      if division:
        divisions.add(division)
      row["_is_player"] = is_player
      row["_division"] = division
      row["payment_selected"] = False
      self._budget_cost_items.append(row)

    type_options = [
      ("Everyone", "all"),
      ("Players", "players"),
      ("Non-players", "non_players"),
    ]
    division_options = [("All divisions", "all"), ("Players without division", "unassigned")]
    division_options.extend(
      (division, "division:" + division)
      for division in sorted(divisions, key=lambda value: value.lower())
    )
    selected_type = self.budget_cost_type_filter.selected_value or "all"
    self.budget_cost_type_filter.items = type_options
    self.budget_cost_type_filter.selected_value = next(
      (value for _, value in type_options if value == selected_type),
      "all",
    )
    selected_division = self.budget_cost_division_filter.selected_value or "all"
    self.budget_cost_division_filter.items = division_options
    self.budget_cost_division_filter.selected_value = next(
      (value for _, value in division_options if value == selected_division),
      "all",
    )
    self._refresh_budget_cost_rows()

  def _matching_budget_cost_items(self):
    query = (self.budget_cost_search.text or "").strip().lower()
    type_filter = self.budget_cost_type_filter.selected_value or "all"
    division_filter = self.budget_cost_division_filter.selected_value or "all"
    matches = []
    for item in self._budget_cost_items:
      entry = item["entry"]
      name = (entry["golfer"]["name"] or "").lower()
      if query and query not in name:
        continue
      if type_filter == "players" and not item["_is_player"]:
        continue
      if type_filter == "non_players" and item["_is_player"]:
        continue
      if division_filter == "unassigned" and (not item["_is_player"] or item["_division"]):
        continue
      if division_filter.startswith("division:") and item["_division"] != division_filter[len("division:"):]:
        continue
      matches.append(item)
    return matches

  def _refresh_budget_cost_rows(self):
    matching_items = self._matching_budget_cost_items()
    self.budget_rows.items = matching_items
    count = len(self._budget_cost_items)
    visible_count = len(matching_items)
    self.budget_cost_match_status.text = (
      f"{visible_count} matching participant" + ("s" if visible_count != 1 else "")
      + f" · {count} total"
    )
    self._update_budget_payment_selection_status()

  def _update_budget_payment_selection_status(self):
    selected_count = sum(
      1 for item in self._budget_cost_items if item["payment_selected"]
    )
    self.budget_payment_selection_status.text = (
      f"{selected_count} participant" + ("s" if selected_count != 1 else "") + " selected."
    )

  def _select_budget_payment_items(self, items, selected):
    for item in items:
      item["payment_selected"] = selected
    self._refresh_budget_cost_rows()

  def _load_budget_target_items(self, rows, tournament):
    tournament_id = tournament.get_id()
    if self._budget_selection_tournament_id != tournament_id:
      self._budget_selected_entry_ids = set()
      self._budget_selection_tournament_id = tournament_id

    self._budget_target_items: list = []
    divisions = set()
    for row in rows:
      entry = row["entry"]
      is_player = entry["is_player"] is not False
      division = (entry["division"] or "").strip() if is_player else ""
      if division:
        divisions.add(division)
      self._budget_target_items.append({
        "entry": entry,
        "name": entry["golfer"]["name"] or "Unnamed participant",
        "participant_label": row["participant_label"],
        "is_player": is_player,
        "division": division,
        "selected": entry.get_id() in self._budget_selected_entry_ids,
      })

    filter_options = [("Everyone", "all"), ("Players", "players"), ("Non-players", "non_players")]
    division_options = [("All divisions", "all"), ("Players without division", "unassigned")]
    division_options.extend(
      (division, "division:" + division)
      for division in sorted(divisions, key=lambda value: value.lower())
    )
    selected_filter = self.budget_target_filter.selected_value or "all"
    self.budget_target_filter.items = filter_options
    self.budget_target_filter.selected_value = next(
      (value for _, value in filter_options if value == selected_filter),
      "all",
    )
    selected_division = self.budget_division_filter.selected_value or "all"
    self.budget_division_filter.items = division_options
    self.budget_division_filter.selected_value = next(
      (value for _, value in division_options if value == selected_division),
      "all",
    )
    self._refresh_budget_target_rows()

  def _matching_budget_target_items(self):
    query = (self.budget_target_search.text or "").strip().lower()
    target_filter = self.budget_target_filter.selected_value or "all"
    division_filter = self.budget_division_filter.selected_value or "all"
    matches = []
    for item in self._budget_target_items:
      if query and query not in item["name"].lower():
        continue
      if target_filter == "players" and not item["is_player"]:
        continue
      if target_filter == "non_players" and item["is_player"]:
        continue
      if division_filter == "unassigned" and (not item["is_player"] or item["division"]):
        continue
      if division_filter.startswith("division:") and item["division"] != division_filter[len("division:"):]:
        continue
      matches.append(item)
    return matches

  def _sync_budget_target_selection(self):
    self._budget_selected_entry_ids = {
      item["entry"].get_id()
      for item in self._budget_target_items
      if item["selected"]
    }

  def _update_budget_target_selection_status(self):
    self._sync_budget_target_selection()
    selected_count = len(self._budget_selected_entry_ids)
    visible_count = len(self._matching_budget_target_items())
    total_count = len(self._budget_target_items)
    self.budget_target_selection_status.text = (
      f"{selected_count} selected · {visible_count} matching · {total_count} participants"
    )

  def _refresh_budget_target_rows(self):
    self.budget_target_rows.items = self._matching_budget_target_items()
    self._update_budget_target_selection_status()

  @staticmethod
  def _money(value):
    return "${:,.2f}".format(value or 0)

  @staticmethod
  def _amount(value):
    return "{:g}".format(value or 0)

  @handle("add_budget_category_button", "click")
  def add_budget_category_button_click(self, **event_args):
    if self.app.current_event is None:
      self.budget_status.text = "Create or select a tournament first."
      return
    result = anvil.server.call(
      "add_budget_category",
      self.app.current_event,
      self.new_budget_category_name.text,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.new_budget_category_name.text = ""
    self.app._load_event_data()
    self.budget_bulk_category_picker.selected_value = result["category"]
    self.budget_status.text = "Expense category added."

  @handle("budget_category_rows", "x-save-budget-category")
  def budget_category_rows_save_budget_category(
    self,
    category,
    name,
    total,
    per_person,
    **event_args,
  ):
    result = anvil.server.call(
      "save_budget_category",
      category,
      name,
      total,
      per_person,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.app._load_event_data()
    self.budget_status.text = f"{name.strip()} saved."

  @handle("budget_category_rows", "x-delete-budget-category")
  def budget_category_rows_delete_budget_category(self, category, **event_args):
    confirmed = confirm(
      f"Delete {category['name']} from this tournament's expenses? Participant selections for this category will also be removed.",
      title="Delete expense category",
    )
    if not confirmed:
      return
    result = anvil.server.call("delete_budget_category", category)
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.app._reload_after_delete()

  @handle("budget_target_filter", "change")
  def budget_target_filter_change(self, **event_args):
    self._refresh_budget_target_rows()

  @handle("budget_division_filter", "change")
  def budget_division_filter_change(self, **event_args):
    self._refresh_budget_target_rows()

  @handle("budget_target_search", "change")
  def budget_target_search_change(self, **event_args):
    self._refresh_budget_target_rows()

  @handle("budget_cost_type_filter", "change")
  def budget_cost_type_filter_change(self, **event_args):
    self._refresh_budget_cost_rows()

  @handle("budget_cost_division_filter", "change")
  def budget_cost_division_filter_change(self, **event_args):
    self._refresh_budget_cost_rows()

  @handle("budget_cost_search", "change")
  def budget_cost_search_change(self, **event_args):
    self._refresh_budget_cost_rows()

  @handle("budget_rows", "x-budget-payment-selection-changed")
  def budget_rows_payment_selection_changed(self, **event_args):
    self._update_budget_payment_selection_status()

  @handle("select_matching_budget_payments_button", "click")
  def select_matching_budget_payments_button_click(self, **event_args):
    self._select_budget_payment_items(self._matching_budget_cost_items(), True)

  @handle("clear_budget_payment_selection_button", "click")
  def clear_budget_payment_selection_button_click(self, **event_args):
    self._select_budget_payment_items(self._budget_cost_items, False)

  @handle("budget_target_rows", "x-budget-target-selection-changed")
  def budget_target_rows_selection_changed(self, **event_args):
    self._update_budget_target_selection_status()

  @handle("select_matching_budget_targets_button", "click")
  def select_matching_budget_targets_button_click(self, **event_args):
    for item in self.budget_target_rows.items or []:
      item["selected"] = True
    self._refresh_budget_target_rows()

  @handle("clear_matching_budget_targets_button", "click")
  def clear_matching_budget_targets_button_click(self, **event_args):
    for item in self.budget_target_rows.items or []:
      item["selected"] = False
    self._refresh_budget_target_rows()

  @handle("assign_budget_category_button", "click")
  def assign_budget_category_button_click(self, **event_args):
    if self.app.current_event is None:
      self.budget_status.text = "Create or select a tournament first."
      return
    category = self.budget_bulk_category_picker.selected_value
    if category is None:
      self.budget_status.text = "Add or select an expense category first."
      return
    self._sync_budget_target_selection()
    entries = [
      item["entry"] for item in self._budget_target_items if item["selected"]
    ]
    if not entries:
      self.budget_status.text = "Select at least one participant."
      return

    result = anvil.server.call(
      "add_budget_category_to_entries",
      self.app.current_event,
      category,
      entries,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.app._load_event_data()
    added = result["added"]
    already_assigned = result["already_assigned"]
    self.budget_status.text = (
      f"{category['name']} added to {added} participant(s)."
      if already_assigned == 0
      else f"{category['name']} added to {added} participant(s); {already_assigned} already shared it."
    )

  @handle("remove_budget_category_button", "click")
  def remove_budget_category_button_click(self, **event_args):
    if self.app.current_event is None:
      self.budget_status.text = "Create or select a tournament first."
      return
    category = self.budget_bulk_category_picker.selected_value
    if category is None:
      self.budget_status.text = "Add or select an expense category first."
      return
    self._sync_budget_target_selection()
    entries = [
      item["entry"] for item in self._budget_target_items if item["selected"]
    ]
    if not entries:
      self.budget_status.text = "Select at least one participant."
      return

    result = anvil.server.call(
      "remove_budget_category_from_entries",
      self.app.current_event,
      category,
      entries,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.app._load_event_data()
    removed = result["removed"]
    not_assigned = result["not_assigned"]
    self.budget_status.text = (
      f"{category['name']} cleared from {removed} participant(s)."
      if not_assigned == 0
      else f"{category['name']} cleared from {removed} participant(s); {not_assigned} selected participant(s) did not share it."
    )

  @handle("save_budget_payments_button", "click")
  def save_budget_payments_button_click(self, **event_args):
    if self.app.current_event is None:
      self.budget_status.text = "Create or select a tournament first."
      return

    selected_items = [
      item for item in self._budget_cost_items if item["payment_selected"]
    ]
    if not selected_items:
      self.budget_status.text = "Select at least one participant first."
      return

    amount = self.budget_bulk_paid_amount.text
    payments = [
      {
        "entry": item["entry"],
        "payment_amount": amount,
      }
      for item in selected_items
    ]

    result = anvil.server.call(
      "add_entry_payments",
      self.app.current_event,
      payments,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.budget_bulk_paid_amount.text = ""
    self.app._load_event_data()
    count = result["saved_count"]
    self.budget_status.text = f"Payments added to Amount Paid totals for {count} participant(s)."
