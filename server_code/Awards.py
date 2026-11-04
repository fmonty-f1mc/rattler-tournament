import anvil.server
import anvil.tables
from anvil.tables import app_tables
import anvil.tables.query as q

from Tracker import _result, _valid_row


@anvil.tables.in_transaction
def _ensure_champion():
  if not any(app_tables.awards.search(is_champion=True)):
    app_tables.awards.add_row(name="Champion", is_champion=True)


@anvil.server.callable(require_user=True)
def list_awards():
  _ensure_champion()
  return sorted(
    (
      award for award in app_tables.awards.search(q.fetch_only("name", "is_champion", "archived"))
      if not award["archived"]
    ),
    key=lambda award: (not award["is_champion"], award["name"].lower()),
  )


@anvil.server.callable(require_user=True)
@anvil.tables.in_transaction
def create_award(name):
  name = (name or "").strip()
  if not name:
    return _result("Enter an award name.")
  awards = list(app_tables.awards.search())
  matching = next((award for award in awards if award["name"].casefold() == name.casefold()), None)
  if matching is not None:
    if not matching["archived"]:
      return _result("That award already exists. Choose it from the award list.")
    matching["archived"] = False
    return _result(award=matching, restored=True)
  is_champion = name.casefold() == "champion"
  if is_champion:
    champion = next((award for award in awards if award["is_champion"]), None)
    if champion is not None:
      if not champion["archived"]:
        return _result(f"The champion award is currently named ‘{champion['name']}’. Choose it from the award list.")
      champion.update(name=name, archived=False)
      return _result(award=champion, restored=True)
  award = app_tables.awards.add_row(name=name, is_champion=is_champion, archived=False)
  return _result(award=award, restored=False)


@anvil.server.callable(require_user=True)
@anvil.tables.in_transaction
def rename_award(award, name):
  if not _valid_row(app_tables.awards, award) or award["archived"]:
    return _result("Choose an available award to rename.")
  name = (name or "").strip()
  if not name:
    return _result("Enter an award name.")
  if name.casefold() == "champion" and not award["is_champion"]:
    return _result("That name is reserved for the champion award.")
  if any(
    other != award and other["name"].casefold() == name.casefold()
    for other in app_tables.awards.search()
  ):
    return _result("That name already belongs to another award.")
  award["name"] = name
  return _result(award=award)


@anvil.server.callable(require_user=True)
@anvil.tables.in_transaction
def delete_award(award):
  if not _valid_row(app_tables.awards, award) or award["archived"]:
    return _result("Choose an available award to delete.")
  # Keep the linked row so historical winner records remain intact.
  award["archived"] = True
  return _result()


@anvil.server.callable(require_user=True)
@anvil.tables.in_transaction
def assign_award(tournament, award, golfer):
  if not _valid_row(app_tables.tournaments, tournament):
    return _result("Select a tournament first.")
  if not _valid_row(app_tables.awards, award) or award["archived"]:
    return _result("Choose an available award.")
  if not _valid_row(app_tables.golfers, golfer):
    return _result("Choose a player from the participant directory.")

  records = list(app_tables.tournament_awards.search(tournament=tournament, award=award))
  if any(record["golfer"] == golfer for record in records):
    return _result("This player already has that award for this year.")
  if award["is_champion"] and records:
    records[0]["golfer"] = golfer
    for extra in records[1:]:
      extra.delete()
    return _result(record=records[0], replaced_champion=True)
  record = app_tables.tournament_awards.add_row(
    tournament=tournament, award=award, golfer=golfer,
  )
  return _result(record=record, replaced_champion=False)


@anvil.server.callable(require_user=True)
def list_award_history():
  return sorted(
    app_tables.tournament_awards.search(q.fetch_only(
      tournament=q.fetch_only("year", "course"),
      award=q.fetch_only("name", "is_champion"),
      golfer=q.fetch_only("name"),
    )),
    key=lambda record: (
      -record["tournament"]["year"],
      not record["award"]["is_champion"],
      record["award"]["name"].lower(),
      record["golfer"]["name"].lower(),
    ),
  )


@anvil.server.callable(require_user=True)
@anvil.tables.in_transaction
def remove_award(record):
  if not _valid_row(app_tables.tournament_awards, record):
    return _result("This award record no longer exists. Refresh the Awards page.")
  record.delete()
  return _result()
