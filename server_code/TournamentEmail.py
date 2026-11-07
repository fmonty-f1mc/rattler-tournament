"""Compose optional email sections from saved tournament data without writes."""
import anvil.server
from anvil.tables import app_tables
import anvil.tables.query as q

from Tracker import (
  _division_names, _entry_is_player, _entry_name, _format_tournament_date,
  _net_standings, _result, _tournament_round_two_scores, _valid_row,
)


SECTIONS = (
  ("details", "Tournament details"),
  ("round_one", "First round groups"),
  ("round_two", "Second round pairings"),
  ("standings", "Overall standings (by net score)"),
  ("division_standings", "Division standings (by net score)"),
  ("awards", "Awards"),
)


def _score(value):
  return "Not posted" if value is None or value <= 0 else f"{value:g}"


def _standing_lines(rows):
  return [
    f"{row['rank']}. {row['player_name']} ({row['division']}) | "
    f"Gross: {_score(row['gross'])} | Net: {_score(row['net'])} | "
    f"Rattler: {_score(row['rattler'])}"
    for row in rows
  ]


def compose_tournament_email(tournament, body, include_sections=None):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  if include_sections is None:
    include_sections = []
  allowed = {key for key, _ in SECTIONS}
  if not isinstance(include_sections, (list, tuple)) or any(
    not isinstance(key, str) or key not in allowed for key in include_sections
  ):
    return _result("Choose valid tournament information to include.")
  selected = set(include_sections)
  body = (body or "").strip()
  if not body and not selected:
    return _result("Enter a message or select tournament information to include.")

  blocks = [body] if body else []
  titles = []
  warnings = []
  entries = []
  round_two_scores = {}
  if selected.intersection(("standings", "division_standings")):
    entries = [
      entry for entry in app_tables.tournament_entries.search(tournament=tournament)
      if _entry_is_player(entry)
    ]
    round_two_scores = _tournament_round_two_scores(tournament)

  for key, title in SECTIONS:
    if key not in selected:
      continue
    lines = []
    if key == "details":
      lines = [f"Year: {tournament['year']}", f"Course: {tournament['course']}"]
      date_label = _format_tournament_date(tournament["event_date"])
      if date_label:
        lines.append(f"Date: {date_label}")
      if tournament["notes"]:
        lines.append(tournament["notes"])
    elif key == "round_one":
      groups = sorted(
        app_tables.tournament_foursomes.search(tournament=tournament),
        key=lambda group: group["sequence"],
      )
      for group in groups:
        label = group["group_label"] or f"Group {group['sequence']}"
        lines.append(f"{label} | Tee time: {group['tee_time'] or 'Not posted'}")
        for slot in range(1, 5):
          entry = group[f"player_{slot}"]
          if entry is not None:
            division = f" ({entry['division']})" if entry["division"] else ""
            lines.append(f"  - {_entry_name(entry)}{division}")
          else:
            lines.append("  - Open spot")
    elif key == "round_two":
      pairs = sorted(
        app_tables.round_two_pairings.search(tournament=tournament),
        key=lambda pair: pair["sequence"],
      )
      for pair in pairs:
        names = [
          _entry_name(pair[slot]) if pair[slot] is not None else "Open spot"
          for slot in ("first_entry", "second_entry")
        ]
        label = pair["pair_label"] or f"Pair {pair['sequence']}"
        lines.append(f"{label}: {' & '.join(names)} | Shared 9-hole score: {_score(pair['score_9'])}")
    elif key == "standings":
      lines = _standing_lines(_net_standings(entries, round_two_scores))
    elif key == "division_standings":
      for division in _division_names(tournament):
        rows = _net_standings(
          [entry for entry in entries if entry["division"] == division],
          round_two_scores,
        )
        lines.append(division)
        lines.extend(_standing_lines(rows) or ["  No scores posted yet."])
    elif key == "awards":
      records = [
        record for record in app_tables.tournament_awards.search(q.fetch_only(
          award=q.fetch_only("name", "is_champion"),
          golfer=q.fetch_only("name"),
        ), tournament=tournament)
        if record["award"] is not None and record["golfer"] is not None
      ]
      lines = [
        f"{record['award']['name']}: {record['golfer']['name']}"
        for record in sorted(records, key=lambda record: (
          not record["award"]["is_champion"],
          record["award"]["name"].casefold(), record["golfer"]["name"].casefold(),
        ))
      ]
    if not lines:
      lines = ["Not posted yet."]
      warnings.append(f"{title}: not posted yet.")
    titles.append(title)
    blocks.append(title + "\n" + "-" * len(title) + "\n" + "\n".join(lines))

  if selected:
    context = f"Tournament: {tournament['year']} · {tournament['course']}"
    blocks.insert(1 if body else 0, context)
  return _result(body="\n\n".join(blocks), section_titles=titles, warnings=warnings)


@anvil.server.callable(require_user=True)
def preview_tournament_email(tournament, body, include_sections=None):
  return compose_tournament_email(tournament, body, include_sections)
