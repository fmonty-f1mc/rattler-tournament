"""Atomic directory edits and round-trip CSV updates; tournament rows stay linked."""
import csv
import hashlib
import io
import json
import math
import re

import anvil.server
from anvil import BlobMedia
from anvil.tables import app_tables, in_transaction
import anvil.tables.query as q

from Tracker import _entry_net_score, _valid_row


FIELDS = ("name", "email", "phone", "city", "state", "handicap", "handicap_official", "active")
HEADERS = ("participant_id", "revision") + FIELDS
LABELS = {"name": "Name", "email": "Email", "phone": "Phone", "city": "City",
          "state": "State", "handicap": "Player handicap",
          "handicap_official": "Official handicap", "active": "Active"}


def _values(row):
  return {key: (bool(row[key]) if key in ("active", "handicap_official") else row[key] if key == "handicap"
                else row[key] or "") for key in FIELDS}


def _revision(row):
  data = json.dumps(_values(row), sort_keys=True, ensure_ascii=True)
  return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _error(message):
  return {"ok": False, "message": message}


def _normalize(values, current):
  if not isinstance(values, dict) or set(values) != set(FIELDS):
    return None, "Use all of the directory columns."
  result = {}
  for key in FIELDS[:5]:
    if not isinstance(values[key], str):
      return None, f"{LABELS[key]} must be text."
    result[key] = values[key].strip()
  if not result["name"]:
    return None, "Name is required."
  # Existing incomplete contact details must not prevent unrelated corrections.
  if result["email"] != current["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(result["email"])):
    return None, "Enter a valid email address."
  handicap = values["handicap"]
  if handicap is None or str(handicap).strip() == "":
    result["handicap"] = None
  else:
    try:
      result["handicap"] = float(handicap)
    except (TypeError, ValueError):
      return None, "Player handicap must be a number or blank."
    if not math.isfinite(result["handicap"]):
      return None, "Player handicap must be a finite number."
  if not isinstance(values["handicap_official"], bool):
    return None, "Official handicap must be TRUE or FALSE."
  if values["handicap_official"] and result["handicap"] is None:
    return None, "Enter a player handicap before marking it official."
  result["handicap_official"] = values["handicap_official"]
  if not isinstance(values["active"], bool):
    return None, "Active must be TRUE or FALSE."
  result["active"] = values["active"]
  return result, None


def _plan(updates):
  if not isinstance(updates, list):
    return None, "Choose directory updates first."
  rows = {row.get_id(): row for row in app_tables.golfers.search()}
  seen = set()
  plan = []
  for update in updates:
    if not isinstance(update, dict):
      return None, "Invalid directory update."
    participant_id = update.get("participant_id")
    if not isinstance(participant_id, str) or participant_id not in rows:
      return None, "A participant no longer exists, or the participant ID is invalid. Reload or export again."
    if participant_id in seen:
      return None, "Each participant ID must appear only once."
    seen.add(participant_id)
    row = rows[participant_id]
    if update.get("revision") != _revision(row):
      return None, f"{row['name']} changed since these details were loaded. Reload or export again before updating."
    current = _values(row)
    values, error = _normalize(update.get("values"), current)
    if error:
      return None, f"{row['name']}: {error}"
    if values != current:
      plan.append((row, current, values))
  final_names = {key: (row["name"] or "").strip().lower() for key, row in rows.items()}
  for row, _, values in plan:
    final_names[row.get_id()] = values["name"].lower()
  name_counts = {}
  for name in final_names.values():
    name_counts[name] = name_counts.get(name, 0) + 1
  for _, current, values in plan:
    if values["name"].lower() != current["name"].strip().lower() and name_counts[values["name"].lower()] > 1:
      return None, f"The name {values['name']} is already used by another participant."
  return plan, None


@anvil.server.callable(require_user=True)
def load_directory_for_editing():
  rows = sorted(app_tables.golfers.search(), key=lambda row: (row["name"] or "").lower())
  return {"rows": rows, "revisions": {row.get_id(): _revision(row) for row in rows}}


@anvil.server.callable(require_user=True)
def get_participant_history(golfer):
  """Join tournament entries and awards without copying persisted row fields."""
  if not _valid_row(app_tables.golfers, golfer):
    return _error("This participant no longer exists. Refresh the directory.")

  years: dict[str, dict] = {}
  for entry in app_tables.tournament_entries.search(
    q.fetch_only("handicap", "is_player", "gross_18", "net_18", tournament=q.fetch_only("year")),
    golfer=golfer,
  ):
    tournament = entry["tournament"]
    # Imported source nets are historical records; live scores use the standings calculation.
    net = entry["net_18"] if entry["net_18"] is not None else _entry_net_score(entry)
    years[tournament.get_id()] = {"tournament": tournament, "entry": entry, "awards": [], "net": net}

  for record in app_tables.tournament_awards.search(
    q.fetch_only(tournament=q.fetch_only("year"), award=q.fetch_only("name", "is_champion")),
    golfer=golfer,
  ):
    tournament = record["tournament"]
    year = years.setdefault(tournament.get_id(), {"tournament": tournament, "entry": None, "awards": [], "net": None})
    year["awards"].append(record["award"])

  for year in years.values():
    # Archived awards remain part of a participant's history.
    year["awards"].sort(key=lambda award: (not award["is_champion"], award["name"].lower()))
  return {"ok": True, "years": sorted(years.values(), key=lambda year: year["tournament"]["year"], reverse=True)}


@anvil.server.callable(require_user=True)
@in_transaction
def save_directory_updates(updates):
  plan, error = _plan(updates)
  if error:
    return _error(error)
  for row, _, values in plan:
    row.update(**values)
  return {"ok": True, "updated_count": len(plan)}


def _csv_cell(value):
  # Neutralize spreadsheet formulas, including international phone prefixes.
  if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n", "'")):
    return "'" + value
  return value


def _read_cell(value):
  if value.startswith("'") and value[1:].startswith(("=", "+", "-", "@", "\t", "\r", "\n", "'")):
    return value[1:]
  return value


@anvil.server.callable(require_user=True)
def export_participant_directory():
  output = io.StringIO(newline="")
  writer = csv.writer(output)
  writer.writerow(HEADERS)
  rows = sorted(app_tables.golfers.search(), key=lambda row: (row["name"] or "").lower())
  for row in rows:
    values = _values(row)
    writer.writerow([row.get_id(), _revision(row)] + [_csv_cell(values[key]) for key in FIELDS])
  return BlobMedia("text/csv", output.getvalue().encode("utf-8-sig"), name="participant-directory.csv")


def _csv_plan(csv_file):
  if csv_file is None:
    return None, "Choose an exported directory CSV first."
  content = csv_file.get_bytes()
  if len(content) > 5 * 1024 * 1024:
    return None, "Choose a CSV smaller than 5 MB."
  try:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
    if reader.fieldnames != list(HEADERS):
      # Column order can change, but missing, extra, or duplicate headers are errors.
      if not reader.fieldnames or len(reader.fieldnames) != len(HEADERS) or set(reader.fieldnames) != set(HEADERS):
        return None, "Keep every original CSV column, including participant_id and revision. Start with Export CSV."
    updates = []
    for line_number, record in enumerate(reader, 2):
      if None in record or any(value is None for value in record.values()):
        return None, f"CSV row {line_number}: the number of cells does not match the headers."
      if not any(record.values()):
        continue
      values = {key: _read_cell(record[key]) for key in FIELDS}
      for field in ("active", "handicap_official"):
        flag = values[field].strip().lower()
        if flag not in ("true", "false"):
          return None, f"CSV row {line_number}: {field} must be TRUE or FALSE."
        values[field] = flag == "true"
      updates.append({"participant_id": record["participant_id"].strip(),
                      "revision": record["revision"].strip(), "values": values})
  except UnicodeDecodeError:
    return None, "Save the CSV as UTF-8 and try again."
  except csv.Error:
    return None, "The selected file is not valid CSV."
  if not updates:
    return None, "The CSV has no participant rows."
  return _plan(updates)


def _display(value, field):
  if field == "active":
    return "Active" if value else "Inactive"
  if field == "handicap_official":
    return "Official" if value else "Not official"
  return "(blank)" if value is None or value == "" else str(value)


@anvil.server.callable(require_user=True)
def preview_directory_csv(csv_file):
  plan, error = _csv_plan(csv_file)
  if error:
    return _error(error)
  changes = []
  for _, current, values in plan:
    for field in FIELDS:
      if current[field] != values[field]:
        changes.append({"name": current["name"], "field": LABELS[field],
                        "before": _display(current[field], field), "after": _display(values[field], field)})
  return {"ok": True, "updated_count": len(plan), "changes": changes}


@anvil.server.callable(require_user=True)
@in_transaction
def apply_directory_csv(csv_file):
  # Re-parse and check revisions inside the transaction; never trust the preview.
  plan, error = _csv_plan(csv_file)
  if error:
    return _error(error)
  for row, _, values in plan:
    row.update(**values)
  return {"ok": True, "updated_count": len(plan)}
