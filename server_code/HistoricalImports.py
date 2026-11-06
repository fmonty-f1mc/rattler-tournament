import anvil.email
"""Preview and atomically import selected year sheets from an XLSX workbook."""

from datetime import datetime
import hashlib
import io
import json
import math
import posixpath
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from anvil import BlobMedia
import anvil.server
from anvil.tables import app_tables, in_transaction
import anvil.tables.query as q

from Tracker import _result, _valid_row

MAX_FILE = 15 * 1024 * 1024
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
STATUSES = {"wd", "dq", "dns", "dnf", "no score", "ns", "withdrawn", "-", "—"}
AWARD_LABELS = {
  "rattler": ("Champion", True), "rattlerchampion": ("Champion", True),
  "champion": ("Champion", True), "nicklaus": ("Nicklaus Award", False),
  "nicklausaward": ("Nicklaus Award", False), "altshot": ("Alt Shot", False),
  "alternateshot": ("Alt Shot", False), "1stroundnet": ("1st Round Net", False),
  "firstroundnet": ("1st Round Net", False), "worst": ("Worst Score", False),
  "worstscore": ("Worst Score", False), "pussy": ("Pussy", False),
}


class WorkbookError(ValueError):
  pass


def _key(value):
  return " ".join(str(value or "").split()).casefold()


def _label(value):
  return re.sub(r"[^a-z0-9]", "", _key(value))


def _name(value):
  value = re.sub(r"\((?:RC|DC|N|[,;\s])+\)", "", str(value or ""), flags=re.I).strip().rstrip("*").strip()
  if value.count(",") == 1:
    last, first = value.split(",")
    value = first.strip() + " " + last.strip()
  return " ".join(value.split())


def _course_key(value):
  return _key(value).replace("forrest", "forest")


def _number(value):
  if isinstance(value, bool) or value is None or _key(value) in STATUSES or str(value).strip() == "":
    return None
  try:
    number = float(value)
  except (TypeError, ValueError):
    return None
  if not math.isfinite(number):
    return None
  return int(number) if number.is_integer() else number


def _display(value):
  return "—" if value is None or value == "" else str(value)


def _column(reference):
  match = re.match(r"[A-Z]+", reference)
  if match is None:
    raise WorkbookError("Invalid cell reference.")
  return match.group()


def _row_number(reference):
  match = re.search(r"[0-9]+", reference)
  if match is None:
    raise WorkbookError("Invalid cell reference.")
  return int(match.group())


def _column_number(column):
  result = 0
  for letter in column:
    result = result * 26 + ord(letter) - 64
  return result


def _read_workbook(data):
  if not data or len(data) > MAX_FILE:
    raise WorkbookError("Choose an .xlsx workbook smaller than 15 MB.")
  try:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
      if len(archive.infolist()) > 2000 or sum(info.file_size for info in archive.infolist()) > 80 * 1024 * 1024:
        raise WorkbookError("This workbook is too large to preview. Export fewer sheets to a new workbook.")
      strings = []
      if "xl/sharedStrings.xml" in archive.namelist():
        strings = ["".join(node.text or "" for node in item.findall(".//m:t", NS))
                   for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", NS)]
      relationships = {item.attrib["Id"]: item.attrib["Target"]
                       for item in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
      sheets = []
      count = 0
      for sheet in ET.fromstring(archive.read("xl/workbook.xml")).findall("m:sheets/m:sheet", NS):
        target = relationships[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        if not path.startswith("xl/"):
          raise WorkbookError("The workbook contains an unsupported external sheet.")
        cells, uncached = {}, []
        for cell in ET.fromstring(archive.read(path)).findall("m:sheetData/m:row/m:c", NS):
          count += 1
          if count > 150000:
            raise WorkbookError("This workbook has too many cells. Export fewer years to a new workbook.")
          reference = cell.attrib.get("r", "")
          if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", reference):
            raise WorkbookError("The workbook contains an invalid cell reference.")
          value_node = cell.find("m:v", NS)
          value = value_node.text if value_node is not None else ""
          kind = cell.attrib.get("t")
          if kind == "s":
            value = strings[int(value)] if value else ""
          elif kind == "inlineStr":
            value = "".join(node.text or "" for node in cell.findall(".//m:t", NS))
          elif kind not in ("str", "e", "b") and value:
            value = _number(value) if _number(value) is not None else value
          if cell.find("m:f", NS) is not None and value in (None, ""):
            uncached.append(reference)
          if value is not None and value != "":
            cells[reference] = value
        sheets.append({"sheet": sheet.attrib["name"], "cells": cells, "uncached": uncached})
      return sheets
  except (zipfile.BadZipFile, ET.ParseError, KeyError, IndexError, ValueError, NotImplementedError, RuntimeError) as error:
    if isinstance(error, WorkbookError):
      raise
    raise WorkbookError("This is not a readable .xlsx workbook. Open it in Excel or Google Sheets and export it as .xlsx.") from error


def _rows(cells):
  rows = {}
  for reference, value in cells.items():
    rows.setdefault(_row_number(reference), {})[_column(reference)] = value
  return rows


def _field(value):
  label = _label(value)
  if label in ("name", "player", "playername", "golfer", "golfername"):
    return "name"
  if label in ("gross", "gross18", "round1gross", "roundonegross"):
    return "gross_18"
  if label in ("hcrc", "hc", "rc", "handicap", "rattlercap"):
    return "handicap"
  if label in ("net", "net18", "round1net", "roundonenet"):
    return "net_18"
  if label in ("altshot", "alternateshot", "gross9", "round2", "roundtwo"):
    return "gross_9"
  if label.startswith("total"):
    return "total"
  return None


def _summary(sheets):
  summary = {}
  for sheet in sheets:
    if re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", sheet["sheet"]):
      continue
    rows = _rows(sheet["cells"])
    for row_number, row in rows.items():
      year_column = next((column for column, value in row.items() if _label(value) == "year"), None)
      champion_column = next((column for column, value in row.items() if _label(value) in ("rattlerchampion", "champion")), None)
      if year_column is None or champion_column is None:
        continue
      nicklaus_column = next((column for column, value in row.items() if _label(value) in ("nicklaus", "nicklausaward")), None)
      course_column = next((column for column, value in row.items() if _label(value) in ("venue", "venues", "course", "courses")), None)
      for number, values in rows.items():
        year = _number(values.get(year_column))
        if number <= row_number or year is None or int(year) != year or not 1900 <= year <= 2099:
          continue
        awards = []
        for column, award_name, champion in ((champion_column, "Champion", True), (nicklaus_column, "Nicklaus Award", False)):
          if column and values.get(column):
            awards.append({"name": award_name, "champion": champion, "winners": [_name(values[column])]})
        summary[int(year)] = {"course": str(values.get(course_column) or "").strip(), "awards": awards}
  return summary


def _resolve_group_name(raw, players):
  cleaned = _name(raw)
  key = _key(cleaned)
  exact = [player["name"] for player in players if _key(player["name"]) == key]
  if len(exact) == 1:
    return exact[0]
  # Only match a unique surname, or a surname with a matching first initial.
  candidates = []
  parts = cleaned.replace(".", "").split()
  for player in players:
    full = player["name"].split()
    if not parts or not full:
      continue
    if len(parts) == 1 and _key(parts[0]) == _key(full[-1]):
      candidates.append(player["name"])
    elif len(parts) == 2 and len(parts[0]) == 1 and _key(parts[1]) == _key(full[-1]) and _key(parts[0]) == _key(full[0][0]):
      candidates.append(player["name"])
  return candidates[0] if len(candidates) == 1 else None


def _parse_year(sheet, year, summary):
  rows = _rows(sheet["cells"])
  errors, warnings = [], []
  header = next(((number, {_field(value): column for column, value in row.items() if _field(value)})
                 for number, row in sorted(rows.items()) if number <= 30
                 and any(_field(value) == "name" for value in row.values())
                 and sum(_field(value) is not None for value in row.values()) >= 3), None)
  document = {"year": year, "sheet": sheet["sheet"], "cells": sheet["cells"],
              "players": [], "awards": [], "groups": [], "course": "", "course_candidates": [],
              "errors": errors, "warnings": warnings}
  if header is None:
    errors.append("No score-table header found. Use Name, Gross, HC/RC, Net, Alt. Shot, Total columns.")
    return document
  header_number, columns = header
  players = document["players"]
  seen = set()
  for number, row in sorted(rows.items()):
    if number <= header_number:
      continue
    source_name = row.get(columns["name"])
    raw = {field: row.get(column) for field, column in columns.items() if field != "name"}
    if not isinstance(source_name, str) or not source_name.strip():
      continue
    if not any(_number(value) is not None or _key(value) in STATUSES for value in raw.values()):
      continue
    name = _name(source_name)
    if _key(name) in seen:
      errors.append(f"Row {number}: duplicate player {name}. Correct the sheet and preview again.")
    seen.add(_key(name))
    player: dict = {"name": name, "source_name": source_name, "row": number, "raw": raw}
    for field in ("gross_18", "handicap", "net_18", "gross_9"):
      value = raw.get(field)
      numeric = _number(value)
      if value not in (None, "") and numeric is None and _key(value) not in STATUSES:
        errors.append(f"Row {number}, {field}: ‘{value}’ is not a number or WD/DQ status.")
      if numeric is not None and field in ("gross_18", "gross_9"):
        if numeric < 0 or int(numeric) != numeric:
          errors.append(f"Row {number}, {field}: golf scores must be positive whole numbers.")
        if numeric == 0:
          numeric = None
      player[field] = numeric
    player["scores"] = " · ".join(f"{label} {_display(raw.get(field))}" for field, label in (
      ("gross_18", "Gross"), ("handicap", "HC/RC"), ("net_18", "Net"), ("gross_9", "Alt. Shot"), ("total", "Total")))
    if player["gross_18"] is not None and player["handicap"] is not None and player["net_18"] is not None:
      calculated = round(player["gross_18"] - player["handicap"], 10)
      if calculated != player["net_18"]:
        warnings.append(f"{name}: source net {player['net_18']}; gross minus HC/RC is {calculated}. Source net is retained; live standings calculate from gross and handicap.")
    total = _number(raw.get("total"))
    if total is not None and total != 0 and player["net_18"] is not None and player["gross_9"] is not None and round(player["net_18"] + player["gross_9"], 10) != total:
      warnings.append(f"{name}: recorded total {total} differs from net plus alternate shot. Original total retained.")
    if any(_key(value) in STATUSES for value in raw.values()):
      warnings.append(f"{name}: WD/DQ or missing-score status retained in the original results.")
    if any("*" in str(value) for value in raw.values()):
      warnings.append(f"{name}: starred value retained in the original results.")
    players.append(player)
  if not players:
    errors.append("No player rows with handicaps or scores were found.")
  if players and not any(player["gross_18"] is not None for player in players):
    warnings.append("No first-round scores are recorded: this year will import participants and handicaps only.")
  if any(player["handicap"] is None for player in players):
    warnings.append("Some handicaps are missing. They stay blank; live net standings require both a gross score and handicap.")
  if sheet["uncached"]:
    warnings.append("Some formulas have no saved result. Recalculate and save the workbook if those cells should contain scores.")

  score_columns = set(columns.values())
  side_cells = [(reference, value) for reference, value in sheet["cells"].items()
                if _column(reference) not in score_columns or _row_number(reference) > max((p["row"] for p in players), default=header_number)]
  courses = [str(value).strip() for reference, value in side_cells if isinstance(value, str)
             and re.search(r"\b(?:golf club|golf course|country club|gc)\b", value, re.I)
             and len(value) < 180]
  # Support a standalone course name near the top, such as “Goshen”.
  if not courses:
    for reference, value in side_cells:
      number = _row_number(reference)
      if number <= 4 and isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z .'-]{2,55}", value.strip()):
        label = _label(value)
        if label not in AWARD_LABELS and not re.search(r"group|rule|tee|shotgun|special|hole|start", value, re.I):
          courses.append(value.strip())
  metadata = summary.get(year, {})
  summary_course = metadata.get("course", "")
  document["course_candidates"] = list(dict.fromkeys(([summary_course] if summary_course else []) + courses))
  document["course"] = summary_course or (courses[0] if courses else "")
  if summary_course and any(_course_key(course) != _course_key(summary_course) for course in courses):
    warnings.append("The year tab and champions summary list different venues. Review the course before importing.")
  if not document["course"]:
    warnings.append("No course was found. Enter the course below before importing.")

  awards = {award["name"]: award for award in metadata.get("awards", [])}
  for reference, label in side_cells:
    if _label(label) not in AWARD_LABELS:
      continue
    column, row_number = _column(reference), _row_number(reference)
    next_values = [value for col, value in sorted(rows[row_number].items(), key=lambda pair: _column_number(pair[0]))
                   if _column_number(col) > _column_number(column)]
    if not next_values or not isinstance(next_values[0], str) or not next_values[0].strip():
      continue
    award_name, champion = AWARD_LABELS[_label(label)]
    recipients = next_values[0].strip()
    if "*" in recipients:
      warnings.append(f"{award_name}: footnoted recipients ‘{recipients}’ retained in source notes; review the recorded award.")
      # A nearby explicit “X was awarded” note identifies the recorded recipient.
      note = " ".join(str(value) for col, value in rows.get(row_number + 1, {}).items()
                      if _column_number(col) >= _column_number(column))
      awarded = re.match(r"(.+?) was awarded\b", note, re.I)
      matches = [p["name"] for p in players if awarded and (_key(p["name"]) == _key(awarded.group(1)) or _key(p["name"].split()[0]) == _key(awarded.group(1)))]
      if len(matches) != 1:
        continue
      winners = matches
    else:
      pieces = re.split(r"\s+and\s+|\s*&\s*|;|\n", recipients, flags=re.I)
      # A comma can separate full names or represent Last, First.
      if len(pieces) == 1 and recipients.count(",") == 1:
        halves = recipients.split(",")
        if all(len(half.split()) >= 2 for half in halves):
          pieces = halves
      winners = list(dict.fromkeys(_name(piece) for piece in pieces if piece.strip()))
      if any(len(winner.split()) < 2 for winner in winners):
        warnings.append(f"{award_name}: abbreviated recipient ‘{recipients}’ is retained in notes but not assigned automatically.")
        continue
    award = {"name": award_name, "champion": champion, "winners": winners}
    if award_name in awards and {_key(w) for w in awards[award_name]["winners"]} != {_key(w) for w in winners}:
      errors.append(f"{award_name} differs between the year sheet and champions summary. Correct the workbook and preview again.")
    else:
      awards[award_name] = award
  document["awards"] = list(awards.values())

  used = set()
  for reference, value in side_cells:
    if not isinstance(value, str) or not re.fullmatch(r"(?:group\s*\d+|\d+(?:st|nd|rd|th)?\s*group)(?:\s+\d{1,2}:\d{2})?", value.strip(), re.I):
      continue
    column, number = _column(reference), _row_number(reference)
    names = []
    for offset in range(1, 5):
      raw_name = rows.get(number + offset, {}).get(column)
      if raw_name in (None, ""):
        break
      resolved = _resolve_group_name(raw_name, players)
      if resolved is None or resolved in used:
        warnings.append(f"{value}: tee-group name ‘{raw_name}’ is unresolved; its slot stays open.")
        names.append(None)
      else:
        names.append(resolved)
        used.add(resolved)
    if names:
      document["groups"].append({"label": value.strip(), "names": names})
  if not document["groups"]:
    warnings.append("Tee groups are not confidently identified. Source cells are archived; no historical groups or alternate-shot partners will be invented.")
  else:
    unassigned = [p["name"] for p in players if p["name"] not in used]
    if unassigned:
      warnings.append("No confirmed tee-group slot for: " + ", ".join(unassigned))
  warnings.append("Alternate-shot partners are not inferred from matching scores.")
  document["warnings"] = list(dict.fromkeys(warnings))
  return document


def _parse(data):
  sheets = _read_workbook(data)
  summary = _summary(sheets)
  documents = []
  for sheet in sheets:
    years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", sheet["sheet"])
    if len(years) == 1:
      documents.append(_parse_year(sheet, int(years[0]), summary))
  if not documents:
    raise WorkbookError("No year tabs were found. Name each year sheet with a four-digit year, such as 2023.")
  counts = {}
  for document in documents:
    counts[document["year"]] = counts.get(document["year"], 0) + 1
  for document in documents:
    if counts[document["year"]] > 1:
      document["errors"].append("More than one tab refers to this year. Keep one year tab before importing.")
  return sorted(documents, key=lambda document: document["year"], reverse=True)


def _fetch_google_workbook(link):
  parsed = urllib.parse.urlparse((link or "").strip())
  match = re.match(r"/spreadsheets/d/([A-Za-z0-9_-]+)(?:/|$)", parsed.path)
  if parsed.scheme != "https" or parsed.hostname != "docs.google.com" or match is None:
    raise WorkbookError("Paste a Google Sheets workbook link, or upload an .xlsx file.")
  url = "https://docs.google.com/spreadsheets/d/" + match.group(1) + "/export?format=xlsx"
  try:
    with urllib.request.urlopen(url, timeout=25) as response:
      data = response.read(MAX_FILE + 1)
  except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout) as error:
    raise WorkbookError("The workbook could not be downloaded. Check its sharing access, or download it as .xlsx and upload it here.") from error
  return data


def _rename_players(document, overrides):
  renamed = {}
  for player in document["players"]:
    name = overrides.get(str(player["row"]), player["name"])
    if not isinstance(name, str) or not name.strip() or len(name) > 150:
      raise WorkbookError(f"{document['year']}: enter a name for each player.")
    renamed[player["name"]] = " ".join(name.split())
    player["name"] = renamed[player["name"]]
  for award in document["awards"]:
    award["winners"] = list(dict.fromkeys(renamed.get(winner, winner) for winner in award["winners"]))
  for group in document["groups"]:
    group["names"] = [renamed.get(name, name) for name in group["names"]]


def _restore_reviewed_names(document):
  """Keep reviewed names/course when the same sheet is previewed again."""
  archives = list(app_tables.historical_imports.search(year=document["year"]))
  if len(archives) != 1:
    return
  saved = archives[0]["data"]
  if saved["sheet"] == document["sheet"] and saved["cells"] == document["cells"]:
    _rename_players(document, {str(player["row"]): player["name"] for player in saved["players"]})
    document["course"] = saved["course"]


@anvil.server.callable(require_user=True)
def preview_historical_workbook(workbook=None, source_url=None):
  try:
    if source_url:
      data = _fetch_google_workbook(source_url)
      workbook = BlobMedia("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", data, name="shared-workbook.xlsx")
    elif workbook is not None:
      data = workbook.get_bytes()
    else:
      raise WorkbookError("Upload an .xlsx file or paste a shared Google Sheets link first.")
    documents = _parse(data)
  except WorkbookError as error:
    return _result(str(error))
  for document in documents:
    _restore_reviewed_names(document)
    plan, conflicts = _plan([document]) if not document["errors"] and document["course"] else (None, [])
    document["conflicts"] = conflicts
    document["selected"] = False
    document["summary"] = f"{document['year']} · {document['sheet']} · {len(document['players'])} players · {sum(p['gross_18'] is not None for p in document['players'])} first-round scores · {sum(len(a['winners']) for a in document['awards'])} award records"
    document["notices"] = "\n".join(document["errors"] + conflicts + document["warnings"])
  return _result(workbook=workbook, years=documents)


def _fingerprint(document):
  content = {key: document[key] for key in ("year", "sheet", "cells", "course", "players", "awards", "groups")}
  return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _plan(documents):
  conflicts, plans = [], []
  by_name = {}
  for golfer in app_tables.golfers.search():
    by_name.setdefault(_key(_name(golfer["name"])), []).append(golfer)
  all_awards = list(app_tables.awards.search())
  for document in documents:
    year = document["year"]
    conflicts.extend(f"{year}: {message}" for message in document["errors"])
    if not document["course"].strip():
      conflicts.append(f"{year}: enter a course before importing.")
    tournaments = list(app_tables.tournaments.search(year=year))
    if len(tournaments) > 1:
      conflicts.append(f"{year}: more than one tournament exists for this year.")
      continue
    tournament = tournaments[0] if tournaments else None
    archive_rows = list(app_tables.historical_imports.search(tournament=tournament)) if tournament is not None else []
    if len(archive_rows) > 1:
      conflicts.append(f"{year}: more than one import archive exists. Resolve the duplicate before importing.")
    fingerprint = _fingerprint(document)
    if archive_rows and any(row["fingerprint"] != fingerprint for row in archive_rows):
      conflicts.append(f"{year}: already imported from a different snapshot. Review the saved original results; existing imports are not overwritten.")
    if tournament is not None and tournament["course"] and _course_key(tournament["course"]) != _course_key(document["course"]):
      conflicts.append(f"{year}: the saved tournament course differs. Review the course in the preview.")
    existing_entries = list(app_tables.tournament_entries.search(tournament=tournament)) if tournament is not None else []
    entry_plan = []
    seen = set()
    for player in document["players"]:
      name = player["name"]
      key = _key(name)
      if not key or len(name) > 150 or key in seen:
        conflicts.append(f"{year}: imported player names must be nonblank and unique ({name}).")
      seen.add(key)
      matches = by_name.get(key, [])
      if len(matches) > 1:
        conflicts.append(f"{year}: multiple directory participants match {name}.")
        continue
      golfer = matches[0] if matches else None
      entries = [entry for entry in existing_entries if golfer is not None and entry["golfer"] == golfer]
      if len(entries) > 1:
        conflicts.append(f"{year}: {name} has duplicate tournament entries.")
        continue
      entry = entries[0] if entries else None
      values = {field: player[field] for field in ("gross_18", "handicap", "net_18", "gross_9")}
      updates = {}
      if entry is not None:
        if entry["is_player"] is False:
          conflicts.append(f"{year}: {name} is already entered as a non-player.")
        for field, value in values.items():
          current = entry[field]
          if current == value:
            continue
          if value is None and _key(player["raw"].get(field)) not in STATUSES:
            continue
          blank = current is None or (current == 0 and (field != "handicap" or entry["gross_18"] in (None, 0)))
          if blank:
            updates[field] = value
          else:
            conflicts.append(f"{year}: {name}'s saved {field} differs from the workbook.")
      entry_plan.append((player, golfer, entry, values, updates))
    award_plan = []
    for source_award in document["awards"]:
      name, champion = source_award["name"], source_award["champion"]
      matches = [award for award in all_awards if (bool(award["is_champion"]) if champion else _key(award["name"]) == _key(name))]
      if len(matches) > 1:
        conflicts.append(f"{year}: multiple awards match {name}.")
        continue
      award = matches[0] if matches else None
      if award is not None and bool(award["is_champion"]) != champion:
        conflicts.append(f"{year}: {name} has a conflicting champion setting.")
      records = list(app_tables.tournament_awards.search(tournament=tournament, award=award)) if tournament is not None and award is not None else []
      expected = {_key(winner) for winner in source_award["winners"]}
      if any(record["golfer"] is None or _key(_name(record["golfer"]["name"])) not in expected for record in records):
        conflicts.append(f"{year}: {name} already has a different recorded recipient.")
      for winner in source_award["winners"]:
        if len(by_name.get(_key(winner), [])) > 1:
          conflicts.append(f"{year}: multiple directory participants match award recipient {winner}.")
      award_plan.append((source_award, award, records))
    plans.append((document, tournament, archive_rows, fingerprint, entry_plan, award_plan))
  return plans, list(dict.fromkeys(conflicts))


def _notes(document, source_name, source_url):
  lines = [f"[Historical workbook: {document['year']}]", f"Source: {source_name} · {document['sheet']}"]
  if source_url:
    lines.append(source_url)
  lines.extend(document["warnings"])
  lines.append("Original sheet cells:")
  for number, row in sorted(_rows(document["cells"]).items()):
    lines.append(" | ".join(f"{column}{number}: {value}" for column, value in sorted(row.items(), key=lambda pair: _column_number(pair[0]))))
  return "\n".join(lines)


@in_transaction
def _execute_import(documents, source_name, source_url):
  plans, conflicts = _plan(documents)
  if conflicts:
    return _result("No selected years were imported.\n" + "\n".join(conflicts))
  golfers = {_key(_name(row["name"])): row for row in app_tables.golfers.search()}
  awards = list(app_tables.awards.search())
  counts = {key: 0 for key in ("tournaments", "players", "entries", "updated_entries", "awards", "archives")}
  imported = []

  def get_golfer(name):
    key = _key(name)
    if key not in golfers:
      golfers[key] = app_tables.golfers.add_row(name=name, email="", phone="", city="", state="", active=True, handicap=None, handicap_official=False)
      counts["players"] += 1
    return golfers[key]

  for document, tournament, archive_rows, fingerprint, entry_plan, award_plan in plans:
    note = _notes(document, source_name, source_url)
    if tournament is None:
      tournament = app_tables.tournaments.add_row(year=document["year"], course=document["course"], event_date=None, notes=note,
        accommodation_total=0, golf_total=0, travel_total=0, other_total=0, budget_categories_initialized=False)
      counts["tournaments"] += 1
    elif not archive_rows:
      tournament["notes"] = ((tournament["notes"] or "").rstrip() + "\n\n" + note).strip()
      if not (tournament["course"] or "").strip():
        tournament["course"] = document["course"]
    entry_by_name = {}
    for player, golfer, entry, values, updates in entry_plan:
      if entry is None:
        entry = app_tables.tournament_entries.add_row(tournament=tournament, golfer=get_golfer(player["name"]), is_player=True, division="",
          accommodation=False, lodging_cost=0, golf_cost=0, travel_cost=0, other_cost=0,
          shares_golf=False, shares_travel=False, shares_other=False, amount_paid=0, **values)
        counts["entries"] += 1
      elif updates:
        entry.update(**updates)
        counts["updated_entries"] += 1
      entry_by_name[player["name"]] = entry
    for source_award, award, records in award_plan:
      if award is None:
        award = next((candidate for candidate in awards if (bool(candidate["is_champion"]) if source_award["champion"] else _key(candidate["name"]) == _key(source_award["name"]))), None)
      if award is None:
        award = app_tables.awards.add_row(name=source_award["name"], is_champion=source_award["champion"], archived=False)
        awards.append(award)
      winner_ids = {record["golfer"].get_id() for record in records}
      for winner in source_award["winners"]:
        golfer = get_golfer(winner)
        if golfer.get_id() not in winner_ids:
          app_tables.tournament_awards.add_row(tournament=tournament, award=award, golfer=golfer)
          winner_ids.add(golfer.get_id())
          counts["awards"] += 1
    if not any(app_tables.tournament_foursomes.search(tournament=tournament)):
      for sequence, group in enumerate(document["groups"], 1):
        names = group["names"] + [None] * (4 - len(group["names"]))
        app_tables.tournament_foursomes.add_row(tournament=tournament, sequence=sequence, group_label=group["label"], tee_time="", grouping_basis="tee_time",
          **{f"player_{slot}": entry_by_name[name] if name else None for slot, name in enumerate(names, 1)})
    if not archive_rows:
      app_tables.historical_imports.add_row(tournament=tournament, year=document["year"], source_name=source_name,
        source_sheet=document["sheet"], source_url=source_url or "", fingerprint=fingerprint,
        data=document, imported_at=datetime.now())
      counts["archives"] += 1
    imported.append(tournament)
  return _result(counts=counts, tournaments=imported, years=[document["year"] for document in documents])


@anvil.server.callable(require_user=True)
def import_historical_workbook(workbook, selections, source_url=""):
  if workbook is None or not isinstance(selections, list) or not selections or len(selections) > 50:
    return _result("Preview a workbook and select between 1 and 50 years first.")
  try:
    documents = _parse(workbook.get_bytes())
  except WorkbookError as error:
    return _result(str(error))
  by_sheet = {document["sheet"]: document for document in documents}
  chosen, seen = [], set()
  for selection in selections:
    if not isinstance(selection, dict) or selection.get("sheet") not in by_sheet or selection["sheet"] in seen:
      return _result("Choose each year once from the workbook preview.")
    seen.add(selection["sheet"])
    document = by_sheet[selection["sheet"]]
    course = selection.get("course")
    overrides = selection.get("names", {})
    if not isinstance(course, str) or len(course) > 200 or not isinstance(overrides, dict):
      return _result("Enter a valid course and player names in the preview.")
    document["course"] = course.strip()
    try:
      _rename_players(document, overrides)
    except WorkbookError as error:
      return _result(str(error))
    chosen.append(document)
  if len({document["year"] for document in chosen}) != len(chosen):
    return _result("Select only one sheet per year.")
  return _execute_import(chosen, workbook.name or "workbook.xlsx", str(source_url or "")[:1000])


@anvil.server.callable(require_user=True)
def list_historical_imports():
  return sorted(app_tables.historical_imports.search(q.fetch_only("year", "source_name", "source_sheet", "imported_at", "tournament")),
                key=lambda row: row["year"], reverse=True)


@anvil.server.callable(require_user=True)
def get_historical_import_source(record):
  if not _valid_row(app_tables.historical_imports, record):
    return _result("Choose a saved import from the list.")
  return _result(data=record["data"])
