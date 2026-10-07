import anvil.google.auth, anvil.google.drive, anvil.google.mail
from anvil.google.drive import app_files
import csv
import io
import math
import random
import re
from datetime import datetime

import anvil.server
from anvil.tables import app_tables


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


def _tournament_email_details(tournament):
  recipient_by_address = {}
  missing_count = 0
  invalid_count = 0
  for entry in app_tables.tournament_entries.search(tournament=tournament):
    golfer = entry["golfer"]
    address = (golfer["email"] or "").strip()
    if not address:
      missing_count += 1
      continue
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
      invalid_count += 1
      continue
    recipient_by_address.setdefault(address.lower(), address)
  return list(recipient_by_address.values()), missing_count, invalid_count


def _entry_name(entry):
  return entry["golfer"]["name"]


def _entry_is_player(entry):
  # Treat entries created before this field existed as players.
  return entry["is_player"] is not False


def _entry_sort_key(entry):
  return (not _entry_is_player(entry), entry["division"] or "", _entry_name(entry).lower())


def _division_names(tournament):
  names = {
    division["name"].strip()
    for division in app_tables.tournament_divisions.search(tournament=tournament)
    if division["name"] and division["name"].strip()
  }
  names.update(
    entry["division"].strip()
    for entry in app_tables.tournament_entries.search(tournament=tournament)
    if _entry_is_player(entry) and entry["division"] and entry["division"].strip()
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


def _round_two_score(entry, pairing_basis):
  if pairing_basis == "net":
    return _entry_net_score(entry)
  return entry["gross_18"]


def _ranked_pairing_entries(entries, pairing_basis):
  if pairing_basis == "net":
    return sorted(
      entries,
      key=lambda entry: (
        _round_two_score(entry, pairing_basis),
        entry["gross_18"],
        _entry_name(entry).lower(),
      ),
    )
  return sorted(
    entries,
    key=lambda entry: (
      _round_two_score(entry, pairing_basis),
      _entry_net_score(entry) if _entry_net_score(entry) is not None else math.inf,
      _entry_name(entry).lower(),
    ),
  )


def _clear_pairings(tournament):
  for pairing in app_tables.rattler_pairings.search(tournament=tournament):
    pairing.delete()


def _delete_pairings_for_entries(pairing_table, entries):
  pairings = {}
  for entry in entries:
    for pairing in pairing_table.search(first_entry=entry):
      pairings[pairing.get_id()] = pairing
    for pairing in pairing_table.search(second_entry=entry):
      pairings[pairing.get_id()] = pairing
  for pairing in pairings.values():
    pairing.delete()
  return len(pairings)


def _clear_tournament_foursomes(tournament):
  if tournament is None:
    return 0
  groups = list(app_tables.tournament_foursomes.search(tournament=tournament))
  for group in groups:
    group.delete()
  return len(groups)


def _delete_budget_shares_for_entries(entries):
  for entry in entries:
    for share in app_tables.budget_shares.search(entry=entry):
      share.delete()


@anvil.server.callable(require_user=True)
def list_committee_news_posts(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  posts = list(app_tables.news_posts.search(tournament=tournament))
  posts.extend(app_tables.news_posts.search(tournament=None))
  return sorted(
    posts,
    key=lambda post: post["created_at"] or datetime.min,
    reverse=True,
  )


@anvil.server.callable(require_user=True)
def save_news_post(post, tournament, title, body):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  title = (title or "").strip()
  body = (body or "").strip()
  if not title:
    return _result("Add a news title.")
  if not body:
    return _result("Add the news text.")

  if post is None:
    post = app_tables.news_posts.add_row(
      title=title,
      body=body,
      tournament=tournament,
      created_at=datetime.now(),
    )
  elif not _valid_row(app_tables.news_posts, post):
    return _result("Choose a news post from the list.")
  elif post["tournament"] is not None and post["tournament"].get_id() != tournament.get_id():
    return _result("Choose a news post for the selected tournament.")
  else:
    post["title"] = title
    post["body"] = body
    post["tournament"] = tournament
  return _result(post=post)


@anvil.server.callable(require_user=True)
def delete_news_post(post, tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  if not _valid_row(app_tables.news_posts, post):
    return _result("Choose a news post from the list.")
  if post["tournament"] is not None and post["tournament"].get_id() != tournament.get_id():
    return _result("Choose a news post for the selected tournament.")
  post.delete()
  return _result()


@anvil.server.callable(require_user=True)
def list_golfers():
  return sorted(app_tables.golfers.search(), key=lambda golfer: (not golfer["active"], golfer["name"].lower()))


@anvil.server.callable(require_user=True)
def import_golfers_from_csv(csv_file):
  if csv_file is None:
    return _result("Choose a CSV file first.")

  content = csv_file.get_bytes()
  if not content:
    return _result("The selected CSV file is empty.")
  try:
    csv_text = content.decode("utf-8-sig")
  except UnicodeDecodeError:
    return _result("Save the CSV as UTF-8 and try again.")

  try:
    reader = csv.DictReader(io.StringIO(csv_text), strict=True)
    headers = reader.fieldnames or []
    rows = list(reader)
  except csv.Error:
    return _result("The selected file is not valid CSV.")

  header_map = {
    header.strip().lower(): header
    for header in headers
    if header and header.strip()
  }
  name_header = header_map.get("name")
  if name_header is None:
    return _result("The CSV needs a header row with a 'name' column.")
  if not rows:
    return _result("The CSV has a header but no player rows.")

  def csv_value(row, field):
    header = header_map.get(field)
    return (row.get(header) or "").strip() if header is not None else ""

  existing_names = {
    (golfer["name"] or "").strip().lower()
    for golfer in app_tables.golfers.search()
  }
  imported_count = 0
  skipped_count = 0
  for row in rows:
    name = (row.get(name_header) or "").strip()
    name_key = name.lower()
    if not name or name_key in existing_names:
      skipped_count += 1
      continue

    app_tables.golfers.add_row(
      name=name,
      email=csv_value(row, "email"),
      phone=csv_value(row, "phone"),
      city=csv_value(row, "city"),
      state=csv_value(row, "state"),
      active=True,
    )
    existing_names.add(name_key)
    imported_count += 1

  return {
    "ok": True,
    "message": f"Imported {imported_count} players; skipped {skipped_count} duplicate or blank-name rows.",
    "imported_count": imported_count,
    "skipped_count": skipped_count,
  }


@anvil.server.callable(require_user=True)
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


@anvil.server.callable(require_user=True)
def set_golfer_active(golfer, active):
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Choose a player from the roster.")
  golfer["active"] = bool(active)
  return _result()


@anvil.server.callable(require_user=True)
def update_golfer(golfer, name, email, phone, city, state):
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Choose a player from the roster.")

  name = (name or "").strip()
  if not name:
    return _result("Add a player name.")
  if any(
    other.get_id() != golfer.get_id()
    and (other["name"] or "").strip().lower() == name.lower()
    for other in app_tables.golfers.search()
  ):
    return _result("That player name is already on the roster.")

  golfer.update(
    name=name,
    email=(email or "").strip(),
    phone=(phone or "").strip(),
    city=(city or "").strip(),
    state=(state or "").strip(),
  )
  return _result()


@anvil.server.callable(require_user=True)
def delete_golfer(golfer):
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Choose a player from the roster.")

  entries = list(app_tables.tournament_entries.search(golfer=golfer))
  cleared_tournaments = set()
  for entry in entries:
    tournament = entry["tournament"]
    if tournament is not None and tournament.get_id() not in cleared_tournaments:
      _clear_tournament_foursomes(tournament)
      cleared_tournaments.add(tournament.get_id())
  rattler_pairing_count = _delete_pairings_for_entries(
    app_tables.rattler_pairings,
    entries,
  )
  round_two_pairing_count = _delete_pairings_for_entries(
    app_tables.round_two_pairings,
    entries,
  )
  _delete_budget_shares_for_entries(entries)
  for entry in entries:
    entry.delete()
  golfer.delete()
  return _result(
    removed_entry_count=len(entries),
    removed_pairing_count=rattler_pairing_count + round_two_pairing_count,
  )


@anvil.server.callable(require_user=True)
def list_tournaments():
  return sorted(app_tables.tournaments.search(), key=lambda tournament: tournament["year"], reverse=True)


@anvil.server.callable(require_user=True)
def delete_tournament(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament.")

  rattler_pairings = list(app_tables.rattler_pairings.search(tournament=tournament))
  round_two_pairings = list(app_tables.round_two_pairings.search(tournament=tournament))
  tournament_foursomes = list(app_tables.tournament_foursomes.search(tournament=tournament))
  entries = list(app_tables.tournament_entries.search(tournament=tournament))
  divisions = list(app_tables.tournament_divisions.search(tournament=tournament))
  budget_categories = list(app_tables.budget_categories.search(tournament=tournament))

  for pairing in rattler_pairings + round_two_pairings + tournament_foursomes:
    pairing.delete()
  _delete_budget_shares_for_entries(entries)
  for category in budget_categories:
    for share in app_tables.budget_shares.search(category=category):
      share.delete()
    category.delete()
  for entry in entries:
    entry.delete()
  for division in divisions:
    division.delete()
  tournament.delete()

  return _result(
    removed_entry_count=len(entries),
    removed_division_count=len(divisions),
    removed_pairing_count=len(rattler_pairings) + len(round_two_pairings),
  )


@anvil.server.callable(require_user=True)
def get_tournament_email_summary(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  recipients, missing_count, invalid_count = _tournament_email_details(tournament)
  return _result(
    recipient_count=len(recipients),
    missing_count=missing_count,
    invalid_count=invalid_count,
  )


@anvil.server.callable(require_user=True)
def send_tournament_email(tournament, subject, body):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  subject = (subject or "").strip()
  body = (body or "").strip()
  if not subject:
    return _result("Enter an email subject.")
  if not body:
    return _result("Enter a message.")

  recipients, missing_count, invalid_count = _tournament_email_details(tournament)
  if not recipients:
    return _result("No participants have a usable email address.")

  anvil.google.mail.send(
    bcc=recipients,
    subject=subject,
    text=body,
  )
  skipped_count = missing_count + invalid_count
  message = f"Email sent to {len(recipients)} unique email addresses."
  if skipped_count:
    message += f" Skipped {skipped_count} participant(s) without a usable email address."
  return _result(
    message,
    sent_count=len(recipients),
    missing_count=missing_count,
    invalid_count=invalid_count,
  )


@anvil.server.callable(require_user=True)
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
    budget_categories_initialized=False,
  )
  return _result(tournament=tournament)


@anvil.server.callable(require_user=True)
def add_golfer_to_tournament(tournament, golfer, is_player=True):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament.")
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Select a player from the roster.")
  if any(app_tables.tournament_entries.search(tournament=tournament, golfer=golfer)):
    return _result("That player is already entered in this tournament.")
  entry = _create_tournament_entry(tournament, golfer, is_player)
  return _result(entry=entry)


def _create_tournament_entry(tournament, golfer, is_player=True):
  if is_player:
    _clear_tournament_foursomes(tournament)
  return app_tables.tournament_entries.add_row(
    tournament=tournament,
    golfer=golfer,
    is_player=bool(is_player),
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


@anvil.server.callable(require_user=True)
def add_golfers_to_tournament(tournament, golfers, is_player=True):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament.")
  if not isinstance(golfers, (list, tuple)) or not golfers:
    return _result("Select one or more golfers from the roster.")

  unique_golfers = []
  seen_ids = set()
  for golfer in golfers:
    if not _valid_row(app_tables.golfers, golfer):
      return _result("Choose golfers from the roster.")
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
    _create_tournament_entry(tournament, golfer, is_player)

  already_entered_count = len(unique_golfers) - len(new_golfers)
  if not new_golfers:
    return _result("All selected golfers are already entered in this tournament.", added_count=0)
  return _result(added_count=len(new_golfers), already_entered_count=already_entered_count)


@anvil.server.callable(require_user=True)
def remove_tournament_entry(tournament, entry):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament.")
  if not _valid_row(app_tables.tournament_entries, entry):
    return _result("This player is no longer entered in a tournament.")

  entry_tournament = entry["tournament"]
  if (
    entry_tournament is None
    or entry_tournament.get_id() != tournament.get_id()
  ):
    return _result("Choose a player entered in the selected tournament.")

  _clear_tournament_foursomes(tournament)

  removed_pairing_count = _delete_pairings_for_entries(
    app_tables.rattler_pairings,
    [entry],
  )
  removed_pairing_count += _delete_pairings_for_entries(
    app_tables.round_two_pairings,
    [entry],
  )
  _delete_budget_shares_for_entries([entry])
  entry.delete()
  return _result(removed_pairing_count=removed_pairing_count)


@anvil.server.callable(require_user=True)
def list_tournament_entries(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  entries = list(app_tables.tournament_entries.search(tournament=tournament))
  return sorted(entries, key=_entry_sort_key)


@anvil.server.callable(require_user=True)
def list_tournament_divisions(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  return _division_names(tournament)


@anvil.server.callable(require_user=True)
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


@anvil.server.callable(require_user=True)
def delete_tournament_division(tournament, name):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  if not isinstance(name, str) or not name.strip():
    return _result("Choose a division to delete.")

  division_name = next(
    (
      existing
      for existing in _division_names(tournament)
      if existing.casefold() == name.strip().casefold()
    ),
    None,
  )
  if division_name is None:
    return _result("That division no longer exists for this tournament.")

  division_key = division_name.casefold()
  unassigned_count = 0
  for entry in app_tables.tournament_entries.search(tournament=tournament):
    assigned_division = entry["division"]
    if (
      _entry_is_player(entry)
      and isinstance(assigned_division, str)
      and assigned_division.strip().casefold() == division_key
    ):
      entry["division"] = ""
      unassigned_count += 1

  for division in app_tables.tournament_divisions.search(tournament=tournament):
    stored_name = division["name"]
    if (
      isinstance(stored_name, str)
      and stored_name.strip().casefold() == division_key
    ):
      division.delete()

  return _result(division_name=division_name, unassigned_count=unassigned_count)


@anvil.server.callable(require_user=True)
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
    if not _entry_is_player(entry):
      return _result("Only players can have field details.")
    entry_id = entry.get_id()
    if entry_id in seen_ids:
      return _result("Each tournament entry can only be saved once.")
    seen_ids.add(entry_id)

    division = details.get("division")
    if division is None:
      division = ""
    if not isinstance(division, str):
      return _result("Choose a valid division or leave it unassigned.")
    division = division.strip()
    if division and division not in divisions:
      return _result("Choose a division created for this tournament or leave it unassigned.")
    handicap_value = _number(details.get("handicap"), "Handicap", allow_blank=True)
    if handicap_value is None:
      return _result("Enter a valid handicap for every tournament entry.")
    updates.append((entry, division, handicap_value))

  for entry, division, handicap in updates:
    entry.update(division=division, handicap=handicap)
  return _result(saved_count=len(updates))


@anvil.server.callable(require_user=True)
def save_round_one_scores(entry, gross):
  gross_value, error = _round_one_score_values(entry, gross)
  if error:
    return _result(error)
  if gross_value is None:
    return _result("Enter a valid gross score.")
  entry.update(gross_18=int(gross_value), net_18=None)
  return _result(net=None)


def _round_one_score_values(entry, gross):
  if not _valid_row(app_tables.tournament_entries, entry):
    return None, "Choose a tournament entry."
  if not _entry_is_player(entry):
    return None, "Only players can enter golf scores."
  gross_value = _number(gross, "Gross score", allow_blank=True)
  if gross_value is None:
    return None, "Enter a valid gross score."
  if int(gross_value) != gross_value:
    return None, "Round-one gross scores must be whole numbers."
  if gross_value < 1:
    return None, "Gross scores must be positive whole numbers."
  return gross_value, None


@anvil.server.callable(require_user=True)
def save_round_one_scores_batch(tournament, scores):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament.")
  if not isinstance(scores, (list, tuple)) or not scores:
    return _result("Enter at least one gross score before saving.")

  updates = []
  seen_ids = set()
  for score in scores:
    if not isinstance(score, dict):
      return _result("Choose valid tournament entries to score.")
    entry = score.get("entry")
    if entry is None or not _valid_row(app_tables.tournament_entries, entry):
      return _result("Choose valid tournament entries to score.")
    entry_tournament = entry["tournament"]
    if entry_tournament is None or entry_tournament.get_id() != tournament.get_id():
      return _result("Choose players from the selected tournament.")
    entry_id = entry.get_id()
    if entry_id in seen_ids:
      return _result("Each player can only be saved once.")
    seen_ids.add(entry_id)

    gross_value, error = _round_one_score_values(
      entry,
      score.get("gross"),
    )
    if error:
      return _result(error)
    if gross_value is None:
      return _result("Enter a valid gross score.")
    updates.append((entry, int(gross_value)))

  for entry, gross_value in updates:
    entry.update(gross_18=gross_value, net_18=None)
  return _result(saved_count=len(updates))


@anvil.server.callable(require_user=True)
def get_net_standings(tournament):
  entries = [entry for entry in list_tournament_entries(tournament) if _entry_is_player(entry)]
  return _net_standings(entries)


def _net_standings(entries):
  scored = [entry for entry in entries if (_entry_net_score(entry) or 0) > 0]
  scored = _ranked_entries(scored)
  return [
    {
      "rank": index + 1,
      "player_name": _entry_name(entry),
      "division": entry["division"] or "No division",
      "gross": entry["gross_18"],
      "net": _entry_net_score(entry),
    }
    for index, entry in enumerate(scored)
  ]


@anvil.server.callable
def get_public_tournament_standings():
  tournaments = sorted(
    app_tables.tournaments.search(),
    key=lambda tournament: tournament["year"],
    reverse=True,
  )
  public_standings = []
  for tournament in tournaments:
    player_entries = [
      entry
      for entry in app_tables.tournament_entries.search(tournament=tournament)
      if _entry_is_player(entry)
    ]
    budget_summary = _budget_summary(tournament)
    round_two_pairs = sorted(
      app_tables.round_two_pairings.search(tournament=tournament),
      key=lambda pairing: pairing["sequence"],
    )
    divisions = [
      {
        "name": name,
        "standings": _net_standings(
          [entry for entry in player_entries if entry["division"] == name]
        ),
      }
      for name in _division_names(tournament)
    ]
    public_standings.append({
      "title": f"{tournament['year']} · {tournament['course']}",
      "news_posts": [
        {"title": post["title"], "body": post["body"]}
        for post in sorted(
          app_tables.news_posts.search(tournament=tournament),
          key=lambda post: post["created_at"] or datetime.min,
          reverse=True,
        )
      ],
      "standings": _net_standings(player_entries),
      "divisions": divisions,
      "round_two_pairs": [
        {
          "pair_label": pairing["pair_label"],
          "score_display": (
            f"Shared 9-hole score · {pairing['score_9']}"
            if pairing["score_9"] is not None and pairing["score_9"] > 0
            else "Shared 9-hole score not posted"
          ),
        }
        for pairing in round_two_pairs
      ],
      "budget_summary": {
        "total": budget_summary["total"],
        "paid": budget_summary["paid"],
        "balance": budget_summary["balance"],
        "participants": [
          {
            "name": row["entry"]["golfer"]["name"],
            "participant_label": row["participant_label"],
            "is_player": _entry_is_player(row["entry"]),
            "division": (
              (row["entry"]["division"] or "")
              if _entry_is_player(row["entry"])
              else ""
            ),
            "estimated_share": row["estimated_share"],
            "paid": row["entry"]["amount_paid"] or 0,
            "balance": row["estimated_share"] - (row["entry"]["amount_paid"] or 0),
          }
          for row in budget_summary["rows"]
        ],
      },
    })
  return public_standings


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


@anvil.server.callable(require_user=True)
def build_round_two_pairings(tournament, pairing_basis="net"):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  if pairing_basis not in ("net", "gross"):
    return _result("Choose net or gross score for Round Two pairing order.")
  entries = [entry for entry in list_tournament_entries(tournament) if _entry_is_player(entry)]
  if not entries:
    return _result("Add players to this tournament before building Round Two pairs.")
  if any(
    (_round_two_score(entry, pairing_basis) or 0) <= 0
    for entry in entries
  ):
    return _result(
      f"Enter a first-round {pairing_basis} score for every player before building Round Two pairs."
    )

  ranked_entries = _ranked_pairing_entries(entries, pairing_basis)
  rank_by_id = {
    entry.get_id(): index + 1
    for index, entry in enumerate(ranked_entries)
  }
  existing_rows = list(app_tables.round_two_pairings.search(tournament=tournament))
  pair_count = (len(ranked_entries) + 1) // 2
  pairings = []
  for index in range(pair_count):
    first_entry = ranked_entries[index]
    second_index = len(ranked_entries) - index - 1
    second_entry = ranked_entries[second_index] if second_index != index else None
    sequence = index + 1
    score_9 = next(
      (
        pairing["score_9"]
        for pairing in existing_rows
        if _same_round_two_pair(
          first_entry,
          second_entry,
          pairing["first_entry"],
          pairing["second_entry"],
        )
      ),
      None,
    )
    pairings.append({
      "tournament": tournament,
      "sequence": sequence,
      "pairing_basis": pairing_basis,
      "pair_label": _round_two_pair_label(
        sequence, first_entry, second_entry, rank_by_id
      ),
      "first_entry": first_entry,
      "second_entry": second_entry,
      "score_9": score_9,
      "score_changed": False,
    })

  return _result(pair_count=pair_count, pairings=pairings)


@anvil.server.callable(require_user=True)
def list_round_two_pairings(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  return sorted(
    app_tables.round_two_pairings.search(tournament=tournament),
    key=lambda pairing: pairing["sequence"],
  )


@anvil.server.callable(require_user=True)
def save_round_two_pairings(tournament, assignments):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  entries = [entry for entry in list_tournament_entries(tournament) if _entry_is_player(entry)]
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
  pairing_basis = None
  for assignment in assignments:
    if not isinstance(assignment, dict):
      return _result("Each pairing must have a selected first and second player.")
    assignment_basis = assignment.get("pairing_basis") or "net"
    if assignment_basis not in ("net", "gross"):
      return _result("Generate Round Two pairs by net or gross score before saving.")
    if pairing_basis is None:
      pairing_basis = assignment_basis
    elif assignment_basis != pairing_basis:
      return _result("Regenerate all Round Two pairs using one score order before saving.")
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

  ranked_entries = _ranked_pairing_entries(
    [
      entry
      for entry in entries
      if (_round_two_score(entry, pairing_basis) or 0) > 0
    ],
    pairing_basis,
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
  saved_pairings = list(existing_rows.values())
  saved_score_count = 0
  for sequence, (first_entry, second_entry, score_value, score_changed) in enumerate(
    normalized_assignments, 1
  ):
    existing = existing_rows.pop(sequence, None)
    if not score_changed:
      matching_saved_pair = next(
        (
          pairing
          for pairing in saved_pairings
          if _same_round_two_pair(
            first_entry,
            second_entry,
            pairing["first_entry"],
            pairing["second_entry"],
          )
        ),
        None,
      )
      score_value = (
        matching_saved_pair["score_9"]
        if matching_saved_pair is not None
        else None
      )
    if score_value is not None:
      saved_score_count += 1
    values = {
      "tournament": tournament,
      "sequence": sequence,
      "pairing_basis": pairing_basis,
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


def _build_balanced_foursomes(entries):
  shuffled_entries = list(entries)
  random.shuffle(shuffled_entries)
  group_count = (len(shuffled_entries) + 3) // 4
  base_size, larger_group_count = divmod(len(shuffled_entries), group_count)
  capacities = [
    base_size + (1 if index < larger_group_count else 0)
    for index in range(group_count)
  ]
  groups = []
  entry_index = 0
  for capacity in capacities:
    groups.append(shuffled_entries[entry_index:entry_index + capacity])
    entry_index += capacity
  return groups


@anvil.server.callable(require_user=True)
def build_tournament_foursomes(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  entries = [
    entry for entry in list_tournament_entries(tournament)
    if _entry_is_player(entry)
  ]
  if not entries:
    return _result("Add players to this tournament before building foursomes.")

  groups = _build_balanced_foursomes(entries)
  return _result(
    group_count=len(groups),
    groupings=[
      {
        "sequence": sequence,
        "group_label": f"Group {sequence}",
        "entries": group,
      }
      for sequence, group in enumerate(groups, 1)
    ],
  )


@anvil.server.callable(require_user=True)
def list_tournament_foursomes(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  return sorted(
    app_tables.tournament_foursomes.search(tournament=tournament),
    key=lambda group: group["sequence"],
  )


def _save_tournament_foursome_rows(tournament, groups):
  existing_rows = {
    group["sequence"]: group
    for group in app_tables.tournament_foursomes.search(tournament=tournament)
  }
  for sequence, group_data in enumerate(groups, 1):
    if isinstance(group_data, dict):
      group_entries = group_data["entries"]
      group_label = group_data["group_label"]
      tee_time = group_data["tee_time"]
    else:
      group_entries = group_data
      group_label = None
      tee_time = ""
    players = group_entries + [None] * (4 - len(group_entries))
    group = existing_rows.pop(sequence, None)
    values = {
      "tournament": tournament,
      "sequence": sequence,
      "group_label": group_label or f"Group {sequence}",
      "tee_time": tee_time,
      "grouping_basis": "tee_time",
      "player_1": players[0],
      "player_2": players[1],
      "player_3": players[2],
      "player_4": players[3],
    }
    if group is None:
      app_tables.tournament_foursomes.add_row(**values)
    else:
      group.update(**values)
  for stale_group in existing_rows.values():
    stale_group.delete()


@anvil.server.callable(require_user=True)
def get_or_create_tournament_foursomes(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  existing_groups = list_tournament_foursomes(tournament)
  if existing_groups:
    return existing_groups
  entries = [
    entry for entry in list_tournament_entries(tournament)
    if _entry_is_player(entry)
  ]
  if not entries:
    return []
  _save_tournament_foursome_rows(
    tournament,
    _build_balanced_foursomes(entries),
  )
  return list_tournament_foursomes(tournament)


@anvil.server.callable(require_user=True)
def save_tournament_foursomes(tournament, assignments):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  entries = [
    entry for entry in list_tournament_entries(tournament)
    if _entry_is_player(entry)
  ]
  if not entries:
    return _result("Add players to this tournament before saving foursomes.")
  if not isinstance(assignments, (list, tuple)):
    return _result("Generate foursomes before editing them.")

  entry_by_id = {entry.get_id(): entry for entry in entries}
  assigned_ids = []
  normalized_groups = []
  for sequence, assignment in enumerate(assignments, 1):
    if not isinstance(assignment, dict):
      return _result("Choose players for each group.")

    group_label = assignment.get("group_label", "")
    if group_label is not None and not isinstance(group_label, str):
      return _result("Group names must be text.")
    group_label = (group_label or "").strip() or f"Group {sequence}"
    tee_time = assignment.get("tee_time", "")
    if tee_time is None:
      tee_time = ""
    if not isinstance(tee_time, str):
      return _result("Tee times must be text.")
    tee_time = tee_time.strip()

    group_entries = assignment.get("entries")
    if not isinstance(group_entries, (list, tuple)) or not group_entries:
      return _result("Every group must have at least one player.")
    if len(group_entries) > 4:
      return _result("A foursome cannot have more than four players.")
    normalized_group = []
    for entry in group_entries:
      if entry is None or not hasattr(entry, "get_id"):
        return _result("Choose players from this tournament's field.")
      entry_id = entry.get_id()
      if entry_id not in entry_by_id:
        return _result("Choose players from this tournament's field.")
      assigned_ids.append(entry_id)
      normalized_group.append(entry_by_id[entry_id])
    normalized_groups.append({
      "entries": normalized_group,
      "group_label": group_label,
      "tee_time": tee_time,
    })

  if len(assigned_ids) != len(entries) or set(assigned_ids) != set(entry_by_id):
    return _result("Assign every player exactly once across the groups.")

  _save_tournament_foursome_rows(tournament, normalized_groups)
  return _result(saved_count=len(normalized_groups))


@anvil.server.callable(require_user=True)
def get_division_standings(tournament, division):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  if division not in _division_names(tournament):
    return []
  entries = [
    entry
    for entry in list_tournament_entries(tournament)
    if _entry_is_player(entry) and entry["division"] == division
  ]
  return _net_standings(entries)


@anvil.server.callable(require_user=True)
def build_rattler_pairings(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  entries = [entry for entry in list_tournament_entries(tournament) if _entry_is_player(entry)]
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


@anvil.server.callable(require_user=True)
def list_rattler_pairings(tournament):
  if not _valid_row(app_tables.tournaments, tournament):
    return []
  return sorted(app_tables.rattler_pairings.search(tournament=tournament), key=lambda pairing: pairing["sequence"])


@anvil.server.callable(require_user=True)
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


def _legacy_budget_category_specs(tournament, entries):
  definitions = (
    ("Accommodation", "accommodation_total", "lodging_cost", False),
    ("Golf", "golf_total", "golf_cost", True),
    ("Travel", "travel_total", "travel_cost", False),
    ("Other", "other_total", "other_cost", False),
  )
  specs = []
  for index, (name, total_column, entry_column, players_only) in enumerate(definitions):
    total = tournament[total_column]
    if total is None:
      total = sum(entry[entry_column] or 0 for entry in entries)

    selected_entry_ids = set()
    for entry in entries:
      if name == "Accommodation":
        selected = bool(entry["accommodation"]) or (entry["lodging_cost"] or 0) > 0
      elif name == "Golf":
        selected = _entry_is_player(entry) and (
          bool(entry["shares_golf"])
          if entry["shares_golf"] is not None
          else (entry["golf_cost"] or 0) > 0
        )
      elif name == "Travel":
        selected = (
          bool(entry["shares_travel"])
          if entry["shares_travel"] is not None
          else (entry["travel_cost"] or 0) > 0
        )
      else:
        selected = (
          bool(entry["shares_other"])
          if entry["shares_other"] is not None
          else (entry["other_cost"] or 0) > 0
        )
      if selected:
        selected_entry_ids.add(entry.get_id())

    specs.append({
      "key": "legacy-{}".format(index),
      "name": name,
      "total": total or 0,
      "players_only": players_only,
      "selected_entry_ids": selected_entry_ids,
      "category": None,
    })
  return specs


def _ensure_budget_categories(tournament, entries=None):
  categories = list(app_tables.budget_categories.search(tournament=tournament))
  if categories:
    tournament["budget_categories_initialized"] = True
    return categories

  entries = list_tournament_entries(tournament) if entries is None else entries
  if tournament["budget_categories_initialized"] is not True:
    for spec in _legacy_budget_category_specs(tournament, entries):
      category = app_tables.budget_categories.add_row(
        tournament=tournament,
        name=spec["name"],
        total=spec["total"],
        players_only=spec["players_only"],
      )
      for entry in entries:
        if entry.get_id() in spec["selected_entry_ids"]:
          app_tables.budget_shares.add_row(entry=entry, category=category)
    categories = list(app_tables.budget_categories.search(tournament=tournament))

  tournament["budget_categories_initialized"] = True
  return categories


@anvil.server.callable(require_user=True)
def add_budget_category(tournament, name):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Choose a tournament.")
  name = (name or "").strip()
  if not name:
    return _result("Enter a category name.")
  categories = _ensure_budget_categories(tournament)
  if any((category["name"] or "").strip().lower() == name.lower() for category in categories):
    return _result("That category already exists for this tournament.")
  category = app_tables.budget_categories.add_row(
    tournament=tournament,
    name=name,
    total=0,
    players_only=False,
  )
  return _result(category=category)


@anvil.server.callable(require_user=True)
def save_budget_category(category, name, total):
  if not _valid_row(app_tables.budget_categories, category):
    return _result("Choose an expense category.")
  name = (name or "").strip()
  if not name:
    return _result("Enter a category name.")
  amount = _number(total, "Category total", allow_blank=False)
  if amount is None or amount < 0:
    return _result("Enter a valid non-negative category total.")
  tournament = category["tournament"]
  if any(
    other.get_id() != category.get_id()
    and (other["name"] or "").strip().lower() == name.lower()
    for other in app_tables.budget_categories.search(tournament=tournament)
  ):
    return _result("That category already exists for this tournament.")
  category.update(name=name, total=amount)
  return _result()


@anvil.server.callable(require_user=True)
def delete_budget_category(category):
  if not _valid_row(app_tables.budget_categories, category):
    return _result("Choose an expense category.")
  for share in app_tables.budget_shares.search(category=category):
    share.delete()
  category.delete()
  return _result()


@anvil.server.callable(require_user=True)
def add_entry_payments(tournament, payments):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Choose a tournament.")
  if not isinstance(payments, (list, tuple)):
    return _result("Choose valid participant payments.")

  tournament_id = tournament.get_id()
  seen_entry_ids = set()
  validated_payments = []
  for payment in payments:
    if not isinstance(payment, dict) or "entry" not in payment or "payment_amount" not in payment:
      return _result("Choose valid participant payments.")
    entry = payment["entry"]
    if not _valid_row(app_tables.tournament_entries, entry):
      return _result("Choose a valid tournament entry.")
    entry_tournament = entry["tournament"]
    if entry_tournament is None or entry_tournament.get_id() != tournament_id:
      return _result("Choose participants from this tournament.")
    entry_id = entry.get_id()
    if entry_id in seen_entry_ids:
      return _result("Each participant can appear only once.")
    payment_amount = _number(payment["payment_amount"], "Payment amount", allow_blank=False)
    if payment_amount is None or payment_amount <= 0:
      return _result(
        "Enter a valid positive payment amount for {}.".format(_entry_name(entry))
      )
    seen_entry_ids.add(entry_id)
    validated_payments.append((entry, payment_amount))

  for entry, payment_amount in validated_payments:
    entry["amount_paid"] = (entry["amount_paid"] or 0) + payment_amount
  return _result(saved_count=len(validated_payments))


@anvil.server.callable(require_user=True)
def add_budget_category_to_entries(tournament, category, entries):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Choose a tournament.")
  if not _valid_row(app_tables.budget_categories, category):
    return _result("Choose an expense category.")
  if not isinstance(entries, (list, tuple)):
    return _result("Choose valid tournament participants.")
  if not entries:
    return _result("Select at least one participant.")

  tournament_id = tournament.get_id()
  available_category_ids = {
    row.get_id()
    for row in app_tables.budget_categories.search(tournament=tournament)
  }
  if category.get_id() not in available_category_ids:
    return _result("Choose an expense category from this tournament.")

  selected_entries = []
  selected_entry_ids = set()
  for entry in entries:
    if not _valid_row(app_tables.tournament_entries, entry):
      return _result("Choose participants from this tournament.")
    entry_tournament = entry["tournament"]
    if entry_tournament is None or entry_tournament.get_id() != tournament_id:
      return _result("Choose participants from this tournament.")
    entry_id = entry.get_id()
    if entry_id in selected_entry_ids:
      continue
    if category["players_only"] and not _entry_is_player(entry):
      return _result(
        "Only players can share the {} category. Remove non-players from your selection.".format(
          category["name"]
        )
      )
    selected_entries.append(entry)
    selected_entry_ids.add(entry_id)

  existing_entry_ids = {
    share["entry"].get_id()
    for share in app_tables.budget_shares.search(category=category)
    if share["entry"] is not None
  }
  entries_to_add = [
    entry for entry in selected_entries if entry.get_id() not in existing_entry_ids
  ]
  for entry in entries_to_add:
    app_tables.budget_shares.add_row(entry=entry, category=category)
  return _result(
    added=len(entries_to_add),
    already_assigned=len(selected_entries) - len(entries_to_add),
  )


@anvil.server.callable(require_user=True)
def remove_budget_category_from_entries(tournament, category, entries):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Choose a tournament.")
  if not _valid_row(app_tables.budget_categories, category):
    return _result("Choose an expense category.")
  if not isinstance(entries, (list, tuple)):
    return _result("Choose valid tournament participants.")
  if not entries:
    return _result("Select at least one participant.")

  tournament_id = tournament.get_id()
  available_category_ids = {
    row.get_id()
    for row in app_tables.budget_categories.search(tournament=tournament)
  }
  if category.get_id() not in available_category_ids:
    return _result("Choose an expense category from this tournament.")

  selected_entry_ids = set()
  for entry in entries:
    if not _valid_row(app_tables.tournament_entries, entry):
      return _result("Choose participants from this tournament.")
    entry_tournament = entry["tournament"]
    if entry_tournament is None or entry_tournament.get_id() != tournament_id:
      return _result("Choose participants from this tournament.")
    selected_entry_ids.add(entry.get_id())

  removed_entry_ids = set()
  for share in app_tables.budget_shares.search(category=category):
    entry = share["entry"]
    if entry is not None and entry.get_id() in selected_entry_ids:
      removed_entry_ids.add(entry.get_id())
      share.delete()

  return _result(
    removed=len(removed_entry_ids),
    not_assigned=len(selected_entry_ids) - len(removed_entry_ids),
  )


def _budget_summary(tournament, migrate_legacy=False):
  if not _valid_row(app_tables.tournaments, tournament):
    return {
      "participants": 0,
      "total": 0,
      "paid": 0,
      "balance": 0,
      "categories": [],
      "rows": [],
    }
  entries = list_tournament_entries(tournament)
  category_rows = list(app_tables.budget_categories.search(tournament=tournament))
  if not category_rows and migrate_legacy:
    category_rows = _ensure_budget_categories(tournament, entries)

  if category_rows:
    category_specs = [
      {
        "key": category.get_id(),
        "name": category["name"],
        "total": category["total"] or 0,
        "players_only": bool(category["players_only"]),
        "category": category,
        "selected_entry_ids": {
          share["entry"].get_id()
          for share in app_tables.budget_shares.search(category=category)
          if share["entry"] is not None
        },
      }
      for category in category_rows
    ]
  elif tournament["budget_categories_initialized"] is not True:
    category_specs = _legacy_budget_category_specs(tournament, entries)
  else:
    category_specs = []

  category_counts = {spec["key"]: 0 for spec in category_specs}
  entry_selection_ids = {}
  for entry in entries:
    selected_ids = {
      spec["key"]
      for spec in category_specs
      if entry.get_id() in spec["selected_entry_ids"]
    }
    entry_selection_ids[entry.get_id()] = selected_ids
    for category_id in selected_ids:
      category_counts[category_id] += 1

  for spec in category_specs:
    count = category_counts[spec["key"]]
    spec["count"] = count
    spec["share"] = spec["total"] / count if count else spec["total"]

  categories = [
    {
      "category": spec["category"],
      "name": spec["name"],
      "total": spec["total"],
      "players_only": spec["players_only"],
      "count": spec["count"],
      "share": spec["share"],
    }
    for spec in category_specs
  ]
  rows = []
  for entry in entries:
    participant_label = (
      (entry["division"] or "Player")
      if _entry_is_player(entry)
      else "Non-player · included in expenses"
    )
    category_shares = [
      {
        "category": spec["category"],
        "name": spec["name"],
        "selected": spec["key"] in entry_selection_ids[entry.get_id()],
        "share": spec["share"],
        "count": spec["count"],
        "players_only": spec["players_only"],
        "entry_is_player": _entry_is_player(entry),
      }
      for spec in category_specs
    ]
    rows.append({
      "entry": entry,
      "participant_label": participant_label,
      "categories": category_shares,
      "estimated_share": sum(
        item["share"] for item in category_shares if item["selected"]
      ),
    })

  total = sum(spec["total"] for spec in category_specs)
  paid = sum(entry["amount_paid"] or 0 for entry in entries)
  return {
    "participants": len(entries),
    "total": total,
    "paid": paid,
    "balance": total - paid,
    "categories": categories,
    "rows": rows,
  }


@anvil.server.callable(require_user=True)
def get_budget_summary(tournament):
  return _budget_summary(tournament, migrate_legacy=True)
