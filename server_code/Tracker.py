import anvil.server
from anvil.tables import app_tables
import math


DIVISIONS = ("Division 1", "Division 2", "Division 3")


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
  return (entry["division"], _entry_name(entry).lower())


def _clear_pairings(tournament):
  for pairing in app_tables.rattler_pairings.search(tournament=tournament):
    pairing.delete()


@anvil.server.callable
def list_golfers():
  return sorted(app_tables.golfers.search(), key=lambda golfer: (not golfer["active"], golfer["name"].lower()))


@anvil.server.callable
def create_golfer(name, division, handicap):
  name = (name or "").strip()
  if not name:
    return _result("Add a player name.")
  if division not in DIVISIONS:
    return _result("Choose one of the three divisions.")
  handicap_value = _number(handicap, "Handicap", allow_blank=True)
  if handicap_value is None:
    return _result("Enter a valid handicap.")
  if any(golfer["name"].strip().lower() == name.lower() for golfer in app_tables.golfers.search()):
    return _result("That player is already on the roster.")
  golfer = app_tables.golfers.add_row(
    name=name,
    division=division,
    handicap=handicap_value,
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
def update_golfer(golfer, division, handicap):
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Choose a player from the roster.")
  if division not in DIVISIONS:
    return _result("Choose one of the three divisions.")
  handicap_value = _number(handicap, "Handicap", allow_blank=True)
  if handicap_value is None:
    return _result("Enter a valid handicap.")
  golfer.update(division=division, handicap=handicap_value)
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
  entry = app_tables.tournament_entries.add_row(
    tournament=tournament,
    golfer=golfer,
    division=golfer["division"],
    handicap=golfer["handicap"],
    gross_18=0,
    net_18=0,
    accommodation=False,
    lodging_cost=0,
    golf_cost=0,
    travel_cost=0,
    other_cost=0,
    amount_paid=0,
  )
  return _result(entry=entry)


@anvil.server.callable
def list_tournament_entries(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  return sorted(app_tables.tournament_entries.search(tournament=tournament), key=_entry_sort_key)


@anvil.server.callable
def save_round_one_scores(entry, gross, net):
  if not _valid_row(app_tables.tournament_entries, entry):
    return _result("Choose a tournament entry.")
  gross_value = _number(gross, "Gross score", allow_blank=True)
  net_value = _number(net, "Net score", allow_blank=True)
  if gross_value is None or net_value is None:
    return _result("Enter valid gross and net scores.")
  if int(gross_value) != gross_value or int(net_value) != net_value:
    return _result("Round-one gross and net scores must be whole numbers.")
  if gross_value < 1 or net_value < 1:
    return _result("Golf scores must be positive whole numbers.")
  entry.update(gross_18=int(gross_value), net_18=int(net_value))
  return _result()


@anvil.server.callable
def get_net_standings(tournament):
  entries = list_tournament_entries(tournament)
  scored = [entry for entry in entries if entry["net_18"] > 0]
  scored.sort(key=lambda entry: (entry["net_18"], entry["gross_18"] if entry["gross_18"] is not None else 999, _entry_name(entry).lower()))
  return [
    {
      "rank": index + 1,
      "player_name": _entry_name(entry),
      "division": entry["division"],
      "gross": entry["gross_18"],
      "net": entry["net_18"],
    }
    for index, entry in enumerate(scored)
  ]


@anvil.server.callable
def build_rattler_pairings(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  entries = list_tournament_entries(tournament)
  if not entries:
    return _result("Add players to this tournament before building pairings.")
  if any(entry["net_18"] <= 0 for entry in entries):
    return _result("Enter a first-round net score for every player before building pairings.")
  entries.sort(key=lambda entry: (entry["net_18"], _entry_name(entry).lower()))
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
def save_entry_budget(entry, accommodation, lodging, golf, travel, other, paid):
  if not _valid_row(app_tables.tournament_entries, entry):
    return _result("Choose a tournament entry.")
  parsed = {}
  for key, value, label in (
    ("lodging_cost", lodging, "Accommodation cost"),
    ("golf_cost", golf, "Golf cost"),
    ("travel_cost", travel, "Travel cost"),
    ("other_cost", other, "Other cost"),
    ("amount_paid", paid, "Amount paid"),
  ):
    number = _number(value, label, allow_blank=False)
    if number is None or number < 0:
      return _result(f"Enter a valid non-negative value for {label.lower()}.")
    parsed[key] = number
  entry.update(accommodation=bool(accommodation), **parsed)
  return _result()


@anvil.server.callable
def get_budget_summary(tournament):
  entries = list_tournament_entries(tournament)
  total = sum(
    (entry["lodging_cost"] or 0)
    + (entry["golf_cost"] or 0)
    + (entry["travel_cost"] or 0)
    + (entry["other_cost"] or 0)
    for entry in entries
  )
  paid = sum(entry["amount_paid"] or 0 for entry in entries)
  accommodated = sum(1 for entry in entries if entry["accommodation"])
  return {
    "participants": len(entries),
    "accommodated": accommodated,
    "total": total,
    "paid": paid,
    "balance": total - paid,
  }
