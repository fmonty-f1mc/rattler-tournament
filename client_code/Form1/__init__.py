from ._anvil_designer import Form1Template
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
import anvil.users


class Form1(Form1Template):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.current_user = anvil.users.get_user()
    if self.current_user is None:
      open_form("PublicStandings")
      return
    self.current_user_label.text = self.current_user["email"]
    self.current_event = None
    self._field_detail_drafts = {}
    self._overall_standings = []
    self._active_standings = []
    self._budget_target_items = []
    self._budget_cost_items = []
    self._budget_selected_entry_ids = set()
    self._budget_selection_tournament_id = None
    self.standings_scope_picker.items = [("Overall", "overall")]
    self.standings_scope_picker.selected_value = "overall"
    self.standings_sort_by.items = [("Net", "net"), ("Gross", "gross")]
    self.standings_sort_by.selected_value = "net"
    self.event_status.text = ""
    self.entry_status.text = ""
    self.field_status.text = ""
    self.division_status.text = ""
    self.standings_status.text = ""
    self.player_status.text = ""
    self.round_one_status.text = ""
    self.round_two_pairing_status.text = ""
    self.budget_status.text = ""
    self.email_status.text = ""
    self._show_view("event")
    self._show_budget_tab("categories")
    self._load_players()
    self._load_events()

  @handle("sign_out_button", "click")
  def sign_out_button_click(self, **event_args):
    anvil.users.logout(invalidate_client_objects=True)
    open_form("Form1")

  def _show_view(self, name):
    show_tournament_context = name != "players"
    self.selected_tournament_eyebrow.visible = show_tournament_context
    self.current_event_title.visible = show_tournament_context
    self.current_event_subtitle.visible = show_tournament_context
    self.event_picker.visible = show_tournament_context
    self.field_summary.visible = show_tournament_context
    self.event_section.visible = name == "event"
    self.field_section.visible = name == "field"
    self.round_one_section.visible = name == "round_one"
    self.standings_section.visible = name == "standings"
    self.round_two_section.visible = name == "round_two"
    self.player_section.visible = name == "players"
    self.budget_section.visible = name == "budget"
    self.email_section.visible = name == "email"
    tournament_view = name in {
      "event", "field", "round_one", "standings", "round_two", "budget", "email"
    }
    self.tournament_subnav.visible = tournament_view
    for view_name, button in (
      ("event", self.setup_nav),
      ("field", self.field_nav),
      ("round_one", self.round_one_nav),
      ("standings", self.standings_nav),
      ("round_two", self.round_two_nav),
      ("budget", self.budget_nav),
      ("email", self.email_nav),
    ):
      button.role = (
        "tournament-subtab-active" if name == view_name else "tournament-subtab"
      )

  def _show_budget_tab(self, name):
    for tab_name, panel, button in (
      ("categories", self.budget_categories_tab, self.budget_categories_tab_button),
      ("assign", self.budget_assignments_tab, self.budget_assignments_tab_button),
      ("payments", self.budget_payments_tab, self.budget_payments_tab_button),
    ):
      panel.visible = name == tab_name
      button.role = (
        "tournament-subtab-active" if name == tab_name else "tournament-subtab"
      )

  def _load_players(self):
    self.golfers = anvil.server.call("list_golfers")
    self.player_rows.items = self.golfers

  def _load_entry_options(self, entries):
    if self.current_event is None:
      self.entry_options.items = []
      self.entry_status.text = "Create or select a tournament before adding participants."
      return

    entered_ids = {entry["golfer"].get_id() for entry in entries}
    self._entry_options = [
      {
        "golfer": golfer,
        "label": golfer["name"] + (" · inactive" if not golfer["active"] else ""),
        "selected": False,
      }
      for golfer in self.golfers
      if golfer.get_id() not in entered_ids
    ]
    self.entry_options.items = self._entry_options
    if not self._entry_options:
      self.entry_status.text = (
        "Add golfers to the roster first."
        if not self.golfers
        else "All roster golfers are already entered in this tournament."
      )
    else:
      self.entry_status.text = ""

  def _load_events(self, selected=None):
    tournaments = anvil.server.call("list_tournaments")
    self.event_picker.items = [
      (f"{tournament['year']} · {tournament['course']}", tournament)
      for tournament in tournaments
    ]
    selected_id = selected.get_id() if selected is not None else (
      self.current_event.get_id() if self.current_event is not None else None
    )
    self.current_event = next(
      (tournament for tournament in tournaments if tournament.get_id() == selected_id),
      tournaments[0] if tournaments else None,
    )
    self.event_picker.selected_value = self.current_event
    self._load_event_data()

  def _load_event_data(self, capture_field_detail_drafts=True):
    if capture_field_detail_drafts:
      self._capture_field_detail_drafts()
    self.field_status.text = ""
    self.division_status.text = ""
    if self.current_event is None:
      self.delete_tournament_button.visible = False
      self.current_event_title.text = "Create your first tournament"
      self.current_event_subtitle.text = "Add a year and course to get started."
      self.field_summary.text = "No players entered yet"
      self.division_options = []
      self.division_choices = [("No division", "")]
      self.division_list_label.text = "Create or select a tournament first."
      self.division_to_delete_dropdown.items = []
      self.division_to_delete_dropdown.selected_value = None
      self.delete_division_button.enabled = False
      self.standings_scope_picker.items = [("Overall", "overall")]
      self.standings_scope_picker.selected_value = "overall"
      self.field_rows.items = []
      self.score_rows.items = []
      self._overall_standings = []
      self._active_standings = []
      self.standings_rows.items = []
      self.standings_status.text = "Create or select a tournament to see standings."
      self.round_two_pairing_rows.items = []
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
      self._budget_target_items = []
      self._budget_selected_entry_ids = set()
      self._budget_selection_tournament_id = None
      self.budget_target_selection_status.text = "0 participants selected."
      self.new_budget_category_name.text = ""
      self.budget_total.text = "$0.00"
      self.budget_paid.text = "$0.00"
      self.budget_balance.text = "$0.00"
      self.budget_participants.text = "0 participants"
      self.round_one_status.text = ""
      self.round_two_pairing_status.text = ""
      self._load_entry_options([])
      return

    tournament = self.current_event
    self.delete_tournament_button.visible = True
    self.current_event_title.text = f"{tournament['year']} · {tournament['course']}"
    event_date = tournament["event_date"]
    notes = tournament["notes"]
    details = str(event_date) if event_date else "Date not set"
    if notes:
      details = f"{details} · {notes}"
    self.current_event_subtitle.text = details

    self.division_options = anvil.server.call("list_tournament_divisions", tournament)
    self.division_list_label.text = ", ".join(self.division_options) or "No divisions created yet."
    selected_division = self.division_to_delete_dropdown.selected_value
    self.division_to_delete_dropdown.items = [
      (division, division) for division in self.division_options
    ]
    self.division_to_delete_dropdown.selected_value = (
      selected_division
      if selected_division in self.division_options
      else (self.division_options[0] if self.division_options else None)
    )
    self.delete_division_button.enabled = bool(self.division_options)
    self.division_choices = [("No division", "")] + [
      (division, division) for division in self.division_options
    ]
    selected_scope = self.standings_scope_picker.selected_value or "overall"
    scopes = [("Overall", "overall")] + [
      ("Division: " + division, "division:" + division)
      for division in self.division_options
    ]
    self.standings_scope_picker.items = scopes
    if selected_scope != "overall" and selected_scope not in [
      "division:" + division for division in self.division_options
    ]:
      selected_scope = "overall"
    self.standings_scope_picker.selected_value = selected_scope
    entries = anvil.server.call("list_tournament_entries", tournament)
    self._load_entry_options(entries)
    player_entries = [entry for entry in entries if entry["is_player"] is not False]
    self.field_rows.items = []
    field_items = []
    for entry in player_entries:
      entry_id = entry.get_id()
      draft = self._field_detail_drafts.get(entry_id)
      if draft is None:
        division = entry["division"] or ""
        handicap = "" if entry["handicap"] is None else str(entry["handicap"])
      else:
        division = draft["division"] or ""
        handicap = draft["handicap"]
      field_items.append({
        "entry": entry,
        "division_options": self.division_choices,
        "division": division,
        "handicap": handicap,
      })
    self.field_rows.items = field_items
    self.score_rows.items = player_entries
    round_two_pairings = anvil.server.call("list_round_two_pairings", tournament)
    entry_options = [(entry["golfer"]["name"], entry) for entry in player_entries]
    self.round_two_pairing_rows.items = [
      {
        "sequence": pairing["sequence"],
        "pairing_number": f"Pair {pairing['sequence']}",
        "pair_label": pairing["pair_label"],
        "first_entry": pairing["first_entry"],
        "second_entry": pairing["second_entry"],
        "score_9": pairing["score_9"],
        "score_changed": False,
        "entry_options": entry_options,
      }
      for pairing in round_two_pairings
    ]
    self.generate_round_two_pairings_button.text = (
      "Regenerate pairs from Round One"
      if round_two_pairings
      else "Generate pairs from Round One"
    )
    self.round_two_pairing_status.text = (
      ""
      if round_two_pairings
      else "Generate pairs after all Round One scores are entered."
    )
    division_counts = {division: 0 for division in self.division_options}
    missing_division_count = 0
    for entry in player_entries:
      division = entry["division"]
      if division in division_counts:
        division_counts[division] += 1
      else:
        missing_division_count += 1
    non_player_count = len(entries) - len(player_entries)
    player_label = "player" if len(player_entries) == 1 else "players"
    non_player_label = "non-player" if non_player_count == 1 else "non-players"
    self.field_summary.text = (
      f"{len(player_entries)} {player_label} · {non_player_count} {non_player_label}"
      if entries
      else "No players entered yet"
    )
    if division_counts:
      division_summary = "  ·  ".join(
        f"{division}: {count}" for division, count in division_counts.items()
      )
      self.field_summary.text += f"  ·  {division_summary}"
    if missing_division_count:
      self.field_summary.text += f"  ·  {missing_division_count} unassigned"

    self._overall_standings = anvil.server.call("get_net_standings", tournament)
    self._load_standings()
    self.round_one_status.text = ""

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

    self._budget_target_items = []
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

  def _capture_field_detail_drafts(self):
    for item in self._current_field_detail_values():
      entry = item["entry"]
      self._field_detail_drafts[entry.get_id()] = {
        "division": item.get("division"),
        "handicap": item.get("handicap"),
      }

  def _current_field_detail_values(self):
    return [
      {
        "entry": getattr(row, "item")["entry"],
        "division": getattr(row, "division_dropdown").selected_value,
        "handicap": getattr(row, "handicap_box").text,
      }
      for row in self.field_rows.get_components()
    ]

  def _current_round_one_scores(self):
    scores = []
    for row in self.score_rows.get_components():
      gross = getattr(row, "gross_box").text
      if gross is not None and str(gross).strip():
        scores.append({"entry": getattr(row, "item"), "gross": gross})
    return scores

  def _load_standings(self):
    if self.current_event is None:
      self._active_standings = []
      self.standings_rows.items = []
      self.standings_status.text = "Create or select a tournament to see standings."
      return

    scope = self.standings_scope_picker.selected_value or "overall"
    if scope == "overall":
      self._active_standings = self._overall_standings
    else:
      self._active_standings = anvil.server.call(
        "get_division_standings",
        self.current_event,
        scope[len("division:"):],
      )
    self._show_standings()
    if self._active_standings:
      self.standings_status.text = ""
    elif scope == "overall":
      self.standings_status.text = "No scores have been posted for this tournament yet."
    else:
      self.standings_status.text = "No scores have been posted for this division yet."

  def _show_standings(self):
    self.standings_rows.items = self._sort_standings(
      self._active_standings,
      self.standings_sort_by.selected_value,
    )

  def _sort_standings(self, rows, sort_by):
    sort_by = sort_by or "net"
    other_score = "gross" if sort_by == "net" else "net"
    sorted_rows = sorted(
      rows,
      key=lambda row: (
        row[sort_by],
        row[other_score],
        row["player_name"].lower(),
      ),
    )
    return [dict(row, rank=index + 1) for index, row in enumerate(sorted_rows)]

  @staticmethod
  def _money(value):
    return "${:,.2f}".format(value or 0)

  @staticmethod
  def _amount(value):
    return "{:g}".format(value or 0)

  @handle("event_nav", "click")
  def event_nav_click(self, **event_args):
    self._show_view("event")

  @handle("email_nav", "click")
  def email_nav_click(self, **event_args):
    self._show_view("email")

  @handle("setup_nav", "click")
  def setup_nav_click(self, **event_args):
    self._show_view("event")

  @handle("field_nav", "click")
  def field_nav_click(self, **event_args):
    self._show_view("field")

  @handle("create_division_button", "click")
  def create_division_button_click(self, **event_args):
    if self.current_event is None:
      self.division_status.text = "Create or select a tournament first."
      return
    result = anvil.server.call(
      "create_tournament_division",
      self.current_event,
      self.new_division_name.text,
    )
    if not result["ok"]:
      self.division_status.text = result["message"]
      return
    self.new_division_name.text = ""
    self._load_event_data()
    self.division_status.text = f"{result['division_name']} created for this tournament."

  @handle("delete_division_button", "click")
  def delete_division_button_click(self, **event_args):
    if self.current_event is None:
      self.division_status.text = "Create or select a tournament first."
      return
    division = self.division_to_delete_dropdown.selected_value
    if not division:
      self.division_status.text = "Choose a division to delete."
      return
    confirmed = confirm(
      f"Delete {division}? Players assigned to it will have no division, and their scores will be kept.",
      title="Delete division",
    )
    if not confirmed:
      return

    self._capture_field_detail_drafts()
    result = anvil.server.call(
      "delete_tournament_division",
      self.current_event,
      division,
    )
    if not result["ok"]:
      self.division_status.text = result["message"]
      return

    for draft in self._field_detail_drafts.values():
      if draft["division"] == division:
        draft["division"] = ""
    self._load_event_data(capture_field_detail_drafts=False)
    self.division_status.text = (
      f"Deleted {result['division_name']}. Its players now have no division; their scores were kept."
    )

  @handle("save_field_details_button", "click")
  def save_field_details_button_click(self, **event_args):
    if self.current_event is None:
      self.field_status.text = "Create or select a tournament first."
      return
    entry_details = self._current_field_detail_values()
    if not entry_details:
      self.field_status.text = "Add players to this tournament before saving field details."
      return
    result = anvil.server.call(
      "save_tournament_entry_details_batch",
      self.current_event,
      entry_details,
    )
    if not result["ok"]:
      self.field_status.text = result["message"]
      return
    self._load_event_data()
    self.field_status.text = f"Division and handicap saved for {result['saved_count']} players."

  @handle("field_rows", "x-remove-entry")
  def field_rows_remove_entry(self, entry, **event_args):
    name = entry["golfer"]["name"]
    tournament = self.current_event
    confirmed = confirm(
      f"Remove {name} from this tournament? Their scores and expense details for this tournament will be deleted. Any pairings containing them will also be removed, including shared pairing scores for the other player.",
      title="Remove player from tournament",
    )
    if not confirmed:
      return

    entry_id = entry.get_id()
    self._capture_field_detail_drafts()
    result = anvil.server.call("remove_tournament_entry", tournament, entry)
    if not result["ok"]:
      self.field_status.text = result["message"]
      return

    self._field_detail_drafts.pop(entry_id, None)
    self._load_event_data(capture_field_detail_drafts=False)
    pairing_count = result["removed_pairing_count"]
    if pairing_count:
      pairing_label = "pairing" if pairing_count == 1 else "pairings"
      self.field_status.text = (
        f"Removed {name} from this tournament and removed "
        f"{pairing_count} {pairing_label}, including their shared scores."
      )
    else:
      self.field_status.text = f"Removed {name} from this tournament."

  @handle("round_one_nav", "click")
  def round_one_nav_click(self, **event_args):
    self._show_view("round_one")

  @handle("standings_nav", "click")
  def standings_nav_click(self, **event_args):
    self._show_view("standings")

  @handle("standings_scope_picker", "change")
  def standings_scope_picker_change(self, **event_args):
    self._load_standings()

  @handle("standings_sort_by", "change")
  def standings_sort_by_change(self, **event_args):
    self._show_standings()

  @handle("round_two_nav", "click")
  def round_two_nav_click(self, **event_args):
    self._show_view("round_two")

  @handle("generate_round_two_pairings_button", "click")
  def generate_round_two_pairings_button_click(self, **event_args):
    if self.current_event is None:
      self.round_two_pairing_status.text = "Create or select a tournament first."
      return
    result = anvil.server.call("build_round_two_pairings", self.current_event)
    if not result["ok"]:
      self.round_two_pairing_status.text = result["message"]
      return
    self._load_event_data()
    self.round_two_pairing_status.text = (
      f"{result['pair_count']} Round Two pairs generated from Round One standings."
    )

  @handle("round_two_pairing_rows", "x-pairing-changed")
  def round_two_pairing_rows_pairing_changed(self, **event_args):
    self.round_two_pairing_status.text = "Pairing or score changes are not saved yet."

  @handle("save_round_two_pairings_button", "click")
  def save_round_two_pairings_button_click(self, **event_args):
    if self.current_event is None:
      self.round_two_pairing_status.text = "Create or select a tournament first."
      return
    assignments = [
      {
        "first_entry": pairing["first_entry"],
        "second_entry": pairing["second_entry"],
        "score_9": pairing["score_9"],
        "score_changed": pairing["score_changed"],
      }
      for pairing in (self.round_two_pairing_rows.items or [])
    ]
    result = anvil.server.call(
      "save_round_two_pairings",
      self.current_event,
      assignments,
    )
    if not result["ok"]:
      self.round_two_pairing_status.text = result["message"]
      return
    self._load_event_data()
    self.round_two_pairing_status.text = "Round Two pairs and shared scores saved."

  @handle("players_nav", "click")
  def players_nav_click(self, **event_args):
    self._show_view("players")

  @handle("public_view_nav", "click")
  def public_view_nav_click(self, **event_args):
    open_form("PublicStandings")

  @handle("budget_nav", "click")
  def budget_nav_click(self, **event_args):
    self._show_view("budget")

  @handle("budget_categories_tab_button", "click")
  def budget_categories_tab_button_click(self, **event_args):
    self._show_budget_tab("categories")

  @handle("budget_assignments_tab_button", "click")
  def budget_assignments_tab_button_click(self, **event_args):
    self._show_budget_tab("assign")

  @handle("budget_payments_tab_button", "click")
  def budget_payments_tab_button_click(self, **event_args):
    self._show_budget_tab("payments")

  @handle("send_tournament_email_button", "click")
  def send_tournament_email_button_click(self, **event_args):
    if self.current_event is None:
      self.email_status.text = "Create or select a tournament first."
      return

    subject = (self.email_subject.text or "").strip()
    body = (self.email_body.text or "").strip()
    if not subject:
      self.email_status.text = "Enter an email subject."
      return
    if not body:
      self.email_status.text = "Enter a message."
      return

    self.send_tournament_email_button.enabled = False
    try:
      summary = anvil.server.call("get_tournament_email_summary", self.current_event)
    finally:
      self.send_tournament_email_button.enabled = True

    if not summary["ok"]:
      self.email_status.text = summary["message"]
      return
    recipient_count = summary["recipient_count"]
    if not recipient_count:
      self.email_status.text = "No participants have a usable email address."
      return

    skipped_details = []
    if summary["missing_count"]:
      skipped_details.append(f"{summary['missing_count']} without an email address")
    if summary["invalid_count"]:
      skipped_details.append(f"{summary['invalid_count']} with an invalid email address")
    skipped_message = (
      " Participants with " + " and ".join(skipped_details) + " will be skipped."
      if skipped_details else ""
    )
    confirmed = confirm(
      f"Send this message to {recipient_count} unique email addresses for "
      f"{self.current_event['year']} · {self.current_event['course']}? "
      f"Recipients will be BCCed.{skipped_message}",
      title="Email tournament participants",
    )
    if not confirmed:
      return

    self.email_status.text = "Sending email…"
    self.send_tournament_email_button.enabled = False
    try:
      result = anvil.server.call(
        "send_tournament_email",
        self.current_event,
        subject,
        body,
      )
    finally:
      self.send_tournament_email_button.enabled = True

    self.email_status.text = result["message"]

  @handle("add_budget_category_button", "click")
  def add_budget_category_button_click(self, **event_args):
    if self.current_event is None:
      self.budget_status.text = "Create or select a tournament first."
      return
    result = anvil.server.call(
      "add_budget_category",
      self.current_event,
      self.new_budget_category_name.text,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.new_budget_category_name.text = ""
    self._load_event_data()
    self.budget_bulk_category_picker.selected_value = result["category"]
    self.budget_status.text = "Expense category added."

  @handle("budget_category_rows", "x-save-budget-category")
  def budget_category_rows_save_budget_category(
    self,
    category,
    name,
    total,
    **event_args,
  ):
    result = anvil.server.call(
      "save_budget_category",
      category,
      name,
      total,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self._load_event_data()
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
    self._load_event_data()
    self.budget_status.text = "Expense category deleted."

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
    if self.current_event is None:
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
      self.current_event,
      category,
      entries,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self._load_event_data()
    added = result["added"]
    already_assigned = result["already_assigned"]
    self.budget_status.text = (
      f"{category['name']} added to {added} participant(s)."
      if already_assigned == 0
      else f"{category['name']} added to {added} participant(s); {already_assigned} already shared it."
    )

  @handle("remove_budget_category_button", "click")
  def remove_budget_category_button_click(self, **event_args):
    if self.current_event is None:
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
      self.current_event,
      category,
      entries,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self._load_event_data()
    removed = result["removed"]
    not_assigned = result["not_assigned"]
    self.budget_status.text = (
      f"{category['name']} cleared from {removed} participant(s)."
      if not_assigned == 0
      else f"{category['name']} cleared from {removed} participant(s); {not_assigned} selected participant(s) did not share it."
    )

  @handle("event_picker", "change")
  def event_picker_change(self, **event_args):
    self.current_event = self.event_picker.selected_value
    self._load_event_data()

  @handle("create_tournament_button", "click")
  def create_tournament_button_click(self, **event_args):
    result = anvil.server.call(
      "create_tournament",
      self.tournament_year.text,
      self.course_name.text,
      self.event_date.date,
      self.tournament_notes.text,
    )
    if not result["ok"]:
      self.event_status.text = result["message"]
      return
    self.tournament_year.text = ""
    self.course_name.text = ""
    self.tournament_notes.text = ""
    self.event_date.date = None
    self.event_status.text = "Tournament created. Add this year's players below."
    self._load_events(selected=result["tournament"])

  @handle("delete_tournament_button", "click")
  def delete_tournament_button_click(self, **event_args):
    tournament = self.current_event
    if tournament is None:
      return

    title = f"{tournament['year']} · {tournament['course']}"
    confirmed = confirm(
      f"Delete {title}? This permanently removes the tournament, all player entries and expense details, divisions, scores, and pairings. It will also disappear from public standings.",
      title="Delete tournament",
    )
    if not confirmed:
      return

    result = anvil.server.call("delete_tournament", tournament)
    if not result["ok"]:
      self.event_status.text = result["message"]
      return

    self._field_detail_drafts = {}
    self.field_rows.items = []
    self.current_event = None
    self.event_status.text = f"Deleted tournament {title}."
    self._load_events()

  def _add_selected_entries(self, is_player):
    if self.current_event is None:
      self.entry_status.text = "Create or select a tournament first."
      return
    selected_golfers = [option["golfer"] for option in self._entry_options if option["selected"]]
    result = anvil.server.call(
      "add_golfers_to_tournament",
      self.current_event,
      selected_golfers,
      is_player,
    )
    if not result["ok"]:
      self.entry_status.text = result["message"]
      return
    self._load_event_data()
    added_count = result["added_count"]
    participant_label = "player" if is_player else "non-player"
    if added_count == 1:
      self.entry_status.text = f"{participant_label.capitalize()} added to this year's tournament."
    else:
      self.entry_status.text = f"{added_count} {participant_label}s added to this year's tournament."
    skipped_count = result.get("already_entered_count", 0)
    if skipped_count:
      self.entry_status.text += f" {skipped_count} already entered were skipped."

  @handle("add_players_button", "click")
  def add_players_button_click(self, **event_args):
    self._add_selected_entries(True)

  @handle("add_non_players_button", "click")
  def add_non_players_button_click(self, **event_args):
    self._add_selected_entries(False)

  @handle("create_player_button", "click")
  def create_player_button_click(self, **event_args):
    result = anvil.server.call(
      "create_golfer",
      self.player_name.text,
      self.player_email.text,
      self.player_phone.text,
      self.player_city.text,
      self.player_state.text,
    )
    if not result["ok"]:
      self.player_status.text = result["message"]
      return
    self.player_name.text = ""
    self.player_email.text = ""
    self.player_phone.text = ""
    self.player_city.text = ""
    self.player_state.text = ""
    self.player_status.text = "Player added to the roster."
    self._load_players()
    self._load_event_data()

  @handle("import_players_button", "click")
  def import_players_button_click(self, **event_args):
    csv_file = self.player_csv_file.file
    if csv_file is None:
      self.player_status.text = "Choose a CSV file first."
      return

    self.import_players_button.enabled = False
    try:
      result = anvil.server.call("import_golfers_from_csv", csv_file)
    finally:
      self.import_players_button.enabled = True

    if not result["ok"]:
      self.player_status.text = result["message"]
      return

    self.player_status.text = result["message"]
    self._load_players()
    self._load_event_data()

  @handle("player_rows", "x-toggle-player")
  def player_rows_toggle_player(self, golfer, active, **event_args):
    result = anvil.server.call("set_golfer_active", golfer, active)
    if not result["ok"]:
      self.player_status.text = result["message"]
      return
    self.player_status.text = "Roster updated."
    self._load_players()
    self._load_event_data()

  @handle("player_rows", "x-save-player")
  def player_rows_save_player(self, golfer, name, email, phone, city, state, **event_args):
    result = anvil.server.call("update_golfer", golfer, name, email, phone, city, state)
    if not result["ok"]:
      self.player_status.text = result["message"]
      return
    self.player_status.text = "Player name and details updated."
    self._load_players()
    self._load_event_data()

  @handle("player_rows", "x-delete-player")
  def player_rows_delete_player(self, golfer, **event_args):
    name = golfer["name"]
    confirmed = confirm(
      f"Delete {name} from the roster and all tournaments? This permanently removes their scores, expense details, and tournament pairings. Shared pairing scores for other players in those pairings will also be removed.",
      title="Delete player",
    )
    if not confirmed:
      return

    result = anvil.server.call("delete_golfer", golfer)
    if not result["ok"]:
      self.player_status.text = result["message"]
      return

    entry_count = result["removed_entry_count"]
    entry_label = "tournament entry" if entry_count == 1 else "tournament entries"
    self.player_status.text = f"Deleted {name} and removed {entry_count} {entry_label}."
    self._load_players()
    self._load_event_data()

  @handle("save_round_one_scores_button", "click")
  def save_round_one_scores_button_click(self, **event_args):
    if self.current_event is None:
      self.round_one_status.text = "Create or select a tournament first."
      return
    scores = self._current_round_one_scores()
    if not scores:
      self.round_one_status.text = "Enter at least one gross score before saving."
      return
    result = anvil.server.call(
      "save_round_one_scores_batch",
      self.current_event,
      scores,
    )
    if not result["ok"]:
      self.round_one_status.text = result["message"]
      return
    self._load_event_data()
    self.round_one_status.text = (
      f"Round-one scores saved for {result['saved_count']} players."
    )

  @handle("save_budget_payments_button", "click")
  def save_budget_payments_button_click(self, **event_args):
    if self.current_event is None:
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
      self.current_event,
      payments,
    )
    if not result["ok"]:
      self.budget_status.text = result["message"]
      return
    self.budget_bulk_paid_amount.text = ""
    self._load_event_data()
    count = result["saved_count"]
    self.budget_status.text = f"Payments added to Amount Paid totals for {count} participant(s)."
