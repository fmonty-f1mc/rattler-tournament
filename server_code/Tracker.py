import anvil.server
from anvil.tables import app_tables
import math


def _result(message=None, **values):
  return {"ok": message is None, "message": message, **values}


def _number(value, label, allow_blank=False):
  if value is None or str(value).strip() == "":
    return None if allow_blank else 0
  try:
    number = float(value)
    return number if math.isfinite(number) else None
  except (TypeError, ValueError):
    return None


def _valid_row(table, candidate):
  if candidate is None or not hasattr(candidate, "get_id"):
    return False
  candidate_id = candidate.get_id()
  return any(row.get_id() == candidate_id for row in table.search())


def _entry_name(entry):
  return entry["golfer"]["name"]


def _entry_sort_key(entry):
  return (entry["division"] or "", _entry_name(entry).lower())


def _division_names(tournament):
  names = {
    division["name"].strip()
    for division in app_tables.tournament_divisions.search(tournament=tournament)
    if division["name"] and division["name"].strip()
  }
  names.update(
    entry["division"].strip()
    for entry in app_tables.tournament_entries.search(tournament=tournament)
    if entry["division"] and entry["division"].strip()
  )
  return sorted(names, key=str.lower)


def _entry_net_score(entry):
  gross = entry["gross_18"]
  handicap = entry["handicap"]
  if gross is None or gross <= 0 or handicap is None:
    return None
  return round(gross - handicap, 10)


def _ranked_entries(entries):
  return sorted(
    entries,
    key=lambda entry: (
      _entry_net_score(entry),
      entry["gross_18"],
      _entry_name(entry).lower(),
    ),
  )


def _clear_pairings(tournament):
  for pairing in app_tables.rattler_pairings.search(tournament=tournament):
    pairing.delete()


@anvil.server.callable
def list_golfers():
  return sorted(app_tables.golfers.search(), key=lambda golfer: (not golfer["active"], golfer["name"].lower()))


@anvil.server.callable
def create_golfer(name, email, phone, city, state):
  name = (name or "").strip()
  if not name:
    return _result("Add a player name.")
  if any(golfer["name"].strip().lower() == name.lower() for golfer in app_tables.golfers.search()):
    return _result("That player is already on the roster.")
  golfer = app_tables.golfers.add_row(
    name=name,
    email=(email or "").strip(),
    phone=(phone or "").strip(),
    city=(city or "").strip(),
    state=(state or "").strip(),
    active=True,
  )
  return _result(golfer=golfer)


@anvil.server.callable
def set_golfer_active(golfer, active):
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Choose a player from the roster.")
  golfer["active"] = bool(active)
  return _result()


@anvil.server.callable
def update_golfer(golfer, email, phone, city, state):
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Choose a player from the roster.")
  golfer.update(
    email=(email or "").strip(),
    phone=(phone or "").strip(),
    city=(city or "").strip(),
    state=(state or "").strip(),
  )
  return _result()


@anvil.server.callable
def list_tournaments():
  return sorted(app_tables.tournaments.search(), key=lambda tournament: tournament["year"], reverse=True)


@anvil.server.callable
def create_tournament(year, course, event_date, notes):
  year_value = _number(year, "Year", allow_blank=True)
  course = (course or "").strip()
  if year_value is None or int(year_value) != year_value:
    return _result("Enter a valid tournament year.")
  if not course:
    return _result("Add the course name.")
  year_value = int(year_value)
  if any(tournament["year"] == year_value for tournament in app_tables.tournaments.search()):
    return _result("A tournament for that year already exists. Select it from the event list.")
  tournament = app_tables.tournaments.add_row(
    year=year_value,
    course=course,
    event_date=event_date,
    notes=(notes or "").strip(),
    accommodation_total=0,
    golf_total=0,
    travel_total=0,
    other_total=0,
  )
  return _result(tournament=tournament)


@anvil.server.callable
def add_golfer_to_tournament(tournament, golfer):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament.")
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Select a player from the roster.")
  if any(app_tables.tournament_entries.search(tournament=tournament, golfer=golfer)):
    return _result("That player is already entered in this tournament.")
  entry = _create_tournament_entry(tournament, golfer)
  return _result(entry=entry)


def _create_tournament_entry(tournament, golfer):
  return app_tables.tournament_entries.add_row(
    tournament=tournament,
    golfer=golfer,
    division="",
    handicap=0,
    gross_18=0,
    net_18=0,
    gross_9=0,
    accommodation=False,
    lodging_cost=0,
    golf_cost=0,
    travel_cost=0,
    other_cost=0,
    shares_golf=False,
    shares_travel=False,
    shares_other=False,
    amount_paid=0,
  )


@anvil.server.callable
def add_golfers_to_tournament(tournament, golfers):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament.")
  if not isinstance(golfers, (list, tuple)) or not golfers:
    return _result("Select one or more players from the roster.")

  unique_golfers = []
  seen_ids = set()
  for golfer in golfers:
    if not _valid_row(app_tables.golfers, golfer):
      return _result("Choose players from the roster.")
    golfer_id = golfer.get_id()
    if golfer_id not in seen_ids:
      unique_golfers.append(golfer)
      seen_ids.add(golfer_id)

  entered_ids = {
    entry["golfer"].get_id()
    for entry in app_tables.tournament_entries.search(tournament=tournament)
  }
  new_golfers = [golfer for golfer in unique_golfers if golfer.get_id() not in entered_ids]
  for golfer in new_golfers:
    _create_tournament_entry(tournament, golfer)

  already_entered_count = len(unique_golfers) - len(new_golfers)
  if not new_golfers:
    return _result("All selected players are already entered in this tournament.", added_count=0)
  return _result(added_count=len(new_golfers), already_entered_count=already_entered_count)


@anvil.server.callable
def list_tournament_entries(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  entries = list(app_tables.tournament_entries.search(tournament=tournament))
  for entry in entries:
    net_score = _entry_net_score(entry)
    if net_score is not None and entry["net_18"] != net_score:
      entry["net_18"] = net_score
  return sorted(entries, key=_entry_sort_key)


@anvil.server.callable
def list_tournament_divisions(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  return _division_names(tournament)


@anvil.server.callable
def create_tournament_division(tournament, name):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  name = (name or "").strip()
  if not name:
    return _result("Enter a division name.")
  if any(existing.lower() == name.lower() for existing in _division_names(tournament)):
    return _result("That division already exists for this tournament.")

  app_tables.tournament_divisions.add_row(tournament=tournament, name=name)
  return _result(division_name=name)


@anvil.server.callable
def save_tournament_entry_details_batch(tournament, entry_details):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament.")
  if not isinstance(entry_details, (list, tuple)) or not entry_details:
    return _result("Add players to this tournament before saving field details.")

  divisions = _division_names(tournament)
  updates = []
  seen_ids = set()
  for details in entry_details:
    if not isinstance(details, dict):
      return _result("Choose valid tournament entries.")
    entry = details.get("entry")
    if entry is None or not _valid_row(app_tables.tournament_entries, entry):
      return _result("Choose valid tournament entries.")
    entry_tournament = entry["tournament"]
    if entry_tournament is None or entry_tournament.get_id() != tournament.get_id():
      return _result("Choose entries from the selected tournament.")
    entry_id = entry.get_id()
    if entry_id in seen_ids:
      return _result("Each tournament entry can only be saved once.")
    seen_ids.add(entry_id)

    division = details.get("division")
    if division not in divisions:
      return _result("Choose a division created for this tournament.")
    handicap_value = _number(details.get("handicap"), "Handicap", allow_blank=True)
    if handicap_value is None:
      return _result("Enter a valid handicap for every tournament entry.")
    updates.append((entry, division, handicap_value))

  for entry, division, handicap in updates:
    entry.update(division=division, handicap=handicap)
  return _result(saved_count=len(updates))


@anvil.server.callable
def save_round_one_scores(entry, gross):
  if not _valid_row(app_tables.tournament_entries, entry):
    return _result("Choose a tournament entry.")
  if entry["division"] not in _division_names(entry["tournament"]):
    return _result("Assign a division on the Field page before saving this score.")
  handicap_value = _number(entry["handicap"], "Handicap", allow_blank=True)
  if handicap_value is None:
    return _result("Assign a valid handicap on the Field page before saving this score.")
  gross_value = _number(gross, "Gross score", allow_blank=True)
  if gross_value is None:
    return _result("Enter a valid gross score.")
  if int(gross_value) != gross_value:
    return _result("Round-one gross scores must be whole numbers.")
  if gross_value < 1:
    return _result("Gross scores must be positive whole numbers.")

  net_value = round(gross_value - handicap_value, 10)
  if net_value < 1:
    return _result("Gross score minus handicap must be a positive score.")
  entry.update(
    gross_18=int(gross_value),
    net_18=net_value,
  )
  return _result(net=net_value)


@anvil.server.callable
def get_net_standings(tournament):
  return _net_standings(list_tournament_entries(tournament))


def _net_standings(entries):
  scored = [entry for entry in entries if (_entry_net_score(entry) or 0) > 0]
  scored = _ranked_entries(scored)
  return [
    {
      "rank": index + 1,
      "player_name": _entry_name(entry),
      "division": entry["division"],
      "gross": entry["gross_18"],
      "net": _entry_net_score(entry),
    }
    for index, entry in enumerate(scored)
  ]


def _round_two_pair_label(sequence, first_entry, second_entry, rank_by_id):
  first_rank = rank_by_id.get(first_entry.get_id())
  if second_entry is None:
    if first_rank is None:
      return f"Pair {sequence} · {_entry_name(first_entry)} solo"
    return f"{first_rank}. {_entry_name(first_entry)} · solo"

  second_rank = rank_by_id.get(second_entry.get_id())
  if first_rank is None or second_rank is None:
    return f"Pair {sequence} · {_entry_name(first_entry)} + {_entry_name(second_entry)}"
  return (
    f"{first_rank}. {_entry_name(first_entry)}  +  "
    f"{second_rank}. {_entry_name(second_entry)}"
  )


def _same_round_two_pair(first_entry, second_entry, other_first_entry, other_second_entry):
  return frozenset((first_entry.get_id(), _entry_id_or_none(second_entry))) == frozenset(
    (other_first_entry.get_id(), _entry_id_or_none(other_second_entry))
  )


def _entry_id_or_none(entry):
  return None if entry is None else entry.get_id()


@anvil.server.callable
def build_round_two_pairings(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  entries = list_tournament_entries(tournament)
  if not entries:
    return _result("Add players to this tournament before building Round Two pairs.")
  if any((_entry_net_score(entry) or 0) <= 0 for entry in entries):
    return _result("Enter a first-round net score for every player before building Round Two pairs.")

  ranked_entries = _ranked_entries(entries)
  rank_by_id = {
    entry.get_id(): index + 1
    for index, entry in enumerate(ranked_entries)
  }
  existing_rows = {
    pairing["sequence"]: pairing
    for pairing in app_tables.round_two_pairings.search(tournament=tournament)
  }
  pair_count = (len(ranked_entries) + 1) // 2
  for index in range(pair_count):
    first_entry = ranked_entries[index]
    second_index = len(ranked_entries) - index - 1
    second_entry = ranked_entries[second_index] if second_index != index else None
    sequence = index + 1
    values = {
      "tournament": tournament,
      "sequence": sequence,
      "pair_label": _round_two_pair_label(
        sequence, first_entry, second_entry, rank_by_id
      ),
      "first_entry": first_entry,
      "second_entry": second_entry,
    }
    existing = existing_rows.pop(sequence, None)
    if existing is None:
      values["score_9"] = None
      app_tables.round_two_pairings.add_row(**values)
    else:
      if not _same_round_two_pair(
        first_entry,
        second_entry,
        existing["first_entry"],
        existing["second_entry"],
      ):
        values["score_9"] = None
      existing.update(**values)

  for stale_pairing in existing_rows.values():
    stale_pairing.delete()
  return _result(pair_count=pair_count)


@anvil.server.callable
def list_round_two_pairings(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  return sorted(
    app_tables.round_two_pairings.search(tournament=tournament),
    key=lambda pairing: pairing["sequence"],
  )


@anvil.server.callable
def save_round_two_pairings(tournament, assignments):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  entries = list_tournament_entries(tournament)
  if not entries:
    return _result("Add players to this tournament before saving Round Two pairs.")
  if not isinstance(assignments, (list, tuple)):
    return _result("Generate Round Two pairs before editing them.")

  expected_pair_count = (len(entries) + 1) // 2
  if len(assignments) != expected_pair_count:
    return _result("Generate Round Two pairs before editing them.")

  entry_by_id = {entry.get_id(): entry for entry in entries}
  assigned_ids = []
  normalized_assignments = []
  for assignment in assignments:
    if not isinstance(assignment, dict):
      return _result("Each pairing must have a selected first and second player.")
    first_entry = assignment.get("first_entry")
    second_entry = assignment.get("second_entry")
    if first_entry is None or not hasattr(first_entry, "get_id"):
      return _result("Choose a first player for every pair.")
    if second_entry is not None and not hasattr(second_entry, "get_id"):
      return _result("Choose a player from this tournament's field.")
    first_id = first_entry.get_id()
    second_id = second_entry.get_id() if second_entry is not None else None
    if first_id not in entry_by_id:
      return _result("Choose players from this tournament's field.")
    if second_entry is not None and second_id not in entry_by_id:
      return _result("Choose players from this tournament's field.")
    if second_id == first_id:
      return _result("A player cannot be listed twice in the same pair.")
    assigned_ids.append(first_id)
    if second_id is not None:
      assigned_ids.append(second_id)
    raw_score = assignment.get("score_9")
    score_text = "" if raw_score is None else str(raw_score).strip()
    if not score_text:
      score_value = None
    else:
      parsed_score = _number(score_text, "Round Two score", allow_blank=True)
      if parsed_score is None:
        return _result("Enter a valid shared Round Two score.")
      if int(parsed_score) != parsed_score:
        return _result("Round Two scores must be whole numbers.")
      if parsed_score < 1:
        return _result("Round Two scores must be positive whole numbers.")
      score_value = int(parsed_score)
    normalized_assignments.append((
      first_entry,
      second_entry,
      score_value,
      bool(assignment.get("score_changed")),
    ))

  expected_ids = set(entry_by_id)
  if len(assigned_ids) != len(entries) or set(assigned_ids) != expected_ids:
    return _result("Assign every player exactly once. Leave one player solo when the field is odd.")

  ranked_entries = _ranked_entries(
    [entry for entry in entries if (_entry_net_score(entry) or 0) > 0]
  )
  rank_by_id = (
    {entry.get_id(): index + 1 for index, entry in enumerate(ranked_entries)}
    if len(ranked_entries) == len(entries)
    else {}
  )
  existing_rows = {
    pairing["sequence"]: pairing
    for pairing in app_tables.round_two_pairings.search(tournament=tournament)
  }
  saved_score_count = 0
  for sequence, (first_entry, second_entry, score_value, score_changed) in enumerate(
    normalized_assignments, 1
  ):
    existing = existing_rows.pop(sequence, None)
    if existing is not None and not _same_round_two_pair(
      first_entry,
      second_entry,
      existing["first_entry"],
      existing["second_entry"],
    ) and not score_changed:
      score_value = None
    if score_value is not None:
      saved_score_count += 1
    values = {
      "tournament": tournament,
      "sequence": sequence,
      "pair_label": _round_two_pair_label(
        sequence, first_entry, second_entry, rank_by_id
      ),
      "first_entry": first_entry,
      "second_entry": second_entry,
      "score_9": score_value,
    }
    if existing is None:
      app_tables.round_two_pairings.add_row(**values)
    else:
      existing.update(**values)

  for stale_pairing in existing_rows.values():
    stale_pairing.delete()
  return _result(
    pair_count=len(normalized_assignments),
    scored_pair_count=saved_score_count,
  )


@anvil.server.callable
def get_division_standings(tournament, division):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  if division not in _division_names(tournament):
    return []
  entries = [
    entry
    for entry in list_tournament_entries(tournament)
    if entry["division"] == division
  ]
  return _net_standings(entries)


@anvil.server.callable
def build_rattler_pairings(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  entries = list_tournament_entries(tournament)
  if not entries:
    return _result("Add players to this tournament before building pairings.")
  if any((_entry_net_score(entry) or 0) <= 0 for entry in entries):
    return _result("Enter a first-round net score for every player before building pairings.")
  entries.sort(key=lambda entry: (_entry_net_score(entry), _entry_name(entry).lower()))
  _clear_pairings(tournament)
  pair_count = (len(entries) + 1) // 2
  for index in range(pair_count):
    first_entry = entries[index]
    second_index = len(entries) - index - 1
    second_entry = entries[second_index] if second_index != index else None
    first_rank = index + 1
    second_rank = second_index + 1
    if second_entry is None:
      label = f"{first_rank}. {_entry_name(first_entry)} · solo"
    else:
      label = f"{first_rank}. {_entry_name(first_entry)}  +  {second_rank}. {_entry_name(second_entry)}"
    app_tables.rattler_pairings.add_row(
      tournament=tournament,
      sequence=index + 1,
      pair_label=label,
      first_entry=first_entry,
      second_entry=first_entry if second_entry is None else second_entry,
    )
  return _result(pair_count=pair_count)


@anvil.server.callable
def list_rattler_pairings(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  return sorted(app_tables.rattler_pairings.search(tournament=tournament), key=lambda pairing: pairing["sequence"])


@anvil.server.callable
def save_rattler_card(pairing, scores):
  if not _valid_row(app_tables.rattler_pairings, pairing):
    return _result("Choose a rattler pairing.")
  if len(scores) != 9:
    return _result("Enter nine best-ball hole scores.")
  values = {}
  for hole, score in enumerate(scores, start=1):
    value = _number(score, "Hole score", allow_blank=True)
    if value is not None and value < 1:
      return _result("Each entered hole score must be a positive number.")
    if value is not None and int(value) != value:
      return _result("Hole scores must be whole numbers.")
    values[f"hole_{hole}"] = None if value is None else int(value)
  pairing.update(**values)
  return _result()


@anvil.server.callable
def save_tournament_budget(tournament, accommodation, golf, travel, other):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Choose a tournament.")
  parsed = {}
  for key, value, label in (
    ("accommodation_total", accommodation, "Accommodation total"),
    ("golf_total", golf, "Golf total"),
    ("travel_total", travel, "Travel total"),
    ("other_total", other, "Other total"),
  ):
    number = _number(value, label, allow_blank=False)
    if number is None or number < 0:
      return _result(f"Enter a valid non-negative value for {label.lower()}.")
    parsed[key] = number
  tournament.update(**parsed)
  return _result()


@anvil.server.callable
def save_entry_budget(entry, accommodation, golf, travel, other, paid):
  if not _valid_row(app_tables.tournament_entries, entry):
    return _result("Choose a tournament entry.")
  amount_paid = _number(paid, "Amount paid", allow_blank=False)
  if amount_paid is None or amount_paid < 0:
    return _result("Enter a valid non-negative value for amount paid.")
  entry.update(
    accommodation=bool(accommodation),
    shares_golf=bool(golf),
    shares_travel=bool(travel),
    shares_other=bool(other),
    amount_paid=amount_paid,
  )
  return _result()


@anvil.server.callable
def get_budget_summary(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return {
      "participants": 0,
      "accommodated": 0,
      "total": 0,
      "paid": 0,
      "balance": 0,
      "category_totals": {"accommodation": 0, "golf": 0, "travel": 0, "other": 0},
      "category_counts": {"accommodation": 0, "golf": 0, "travel": 0, "other": 0},
      "rows": [],
    }
  entries = list_tournament_entries(tournament)

  category_totals = {}
  for category, total_column, legacy_column in (
    ("accommodation", "accommodation_total", "lodging_cost"),
    ("golf", "golf_total", "golf_cost"),
    ("travel", "travel_total", "travel_cost"),
    ("other", "other_total", "other_cost"),
  ):
    total_value = tournament[total_column]
    if total_value is None:
      total_value = sum(entry[legacy_column] or 0 for entry in entries)
    category_totals[category] = total_value or 0

  entry_selections = {}
  category_counts = {category: 0 for category in category_totals}
  for entry in entries:
    selections = {
      "accommodation": bool(entry["accommodation"]) or (entry["lodging_cost"] or 0) > 0,
      "golf": (
        bool(entry["shares_golf"])
        if entry["shares_golf"] is not None
        else (entry["golf_cost"] or 0) > 0
      ),
      "travel": (
        bool(entry["shares_travel"])
        if entry["shares_travel"] is not None
        else (entry["travel_cost"] or 0) > 0
      ),
      "other": (
        bool(entry["shares_other"])
        if entry["shares_other"] is not None
        else (entry["other_cost"] or 0) > 0
      ),
    }
    entry_selections[entry.get_id()] = selections
    for category, selected in selections.items():
      if selected:
        category_counts[category] += 1

  category_shares = {
    category: total / category_counts[category] if category_counts[category] else total
    for category, total in category_totals.items()
  }
  rows = []
  for entry in entries:
    selections = entry_selections[entry.get_id()]
    rows.append({
      "entry": entry,
      "shares_accommodation": selections["accommodation"],
      "shares_golf": selections["golf"],
      "shares_travel": selections["travel"],
      "shares_other": selections["other"],
      "accommodation_share": category_shares["accommodation"],
      "golf_share": category_shares["golf"],
      "travel_share": category_shares["travel"],
      "other_share": category_shares["other"],
      "accommodation_count": category_counts["accommodation"],
      "golf_count": category_counts["golf"],
      "travel_count": category_counts["travel"],
      "other_count": category_counts["other"],
      "estimated_share": sum(
        category_shares[category]
        for category, selected in selections.items()
        if selected
      ),
    })

  total = sum(category_totals.values())
  paid = sum(entry["amount_paid"] or 0 for entry in entries)
  accommodated = category_counts["accommodation"]
  return {
    "participants": len(entries),
    "accommodated": accommodated,
    "total": total,
    "paid": paid,
    "balance": total - paid,
    "category_totals": category_totals,
    "category_counts": category_counts,
    "rows": rows,
  }
