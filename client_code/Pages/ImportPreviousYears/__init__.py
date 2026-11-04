from ._anvil_designer import ImportPreviousYearsTemplate
from anvil import *
import anvil.server
from ...Components.Imports.ImportPlayerRow import ImportPlayerRow
from ...Components.Imports.ImportYearRow import ImportYearRow


class ImportPreviousYears(ImportPreviousYearsTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

  def initialize(self, app):
    self.app = app
    self._busy = False
    self._workbook = None
    self._source_url = ''
    self._years = []
    self.year_rows.items = []
    self.import_history.items = []
    self.player_rows.items = []
    self.review_panel.visible = False
    self.preview_panel.visible = False
    self._update_selection()

  def load_history(self):
    records = anvil.server.call('list_historical_imports')
    self.import_history.items = records
    self.empty_history.visible = len(records) == 0

  def _capture_players(self):
    for row in self.player_rows.get_components():
      assert isinstance(row, ImportPlayerRow)
      row.capture()

  def _capture_years(self):
    self._capture_players()
    for row in self.year_rows.get_components():
      assert isinstance(row, ImportYearRow)
      row.capture()

  def _update_selection(self):
    count = sum(1 for document in self._years if document['selected'] and not document['errors'])
    self.selection_status.text = str(count) + ' year(s) selected'
    self.import_years_button.text = 'Import selected years (' + str(count) + ')'
    self.import_years_button.enabled = not self._busy and count > 0
    self.select_all_button.enabled = not self._busy and len(self._years) > 0
    self.clear_selection_button.enabled = not self._busy and len(self._years) > 0

  def _set_busy(self, busy):
    self._busy = busy
    for control in (self.workbook_file, self.workbook_link, self.preview_link_button, self.preview_file_button, self.close_review_button):
      control.enabled = not busy
    for row in self.year_rows.get_components():
      assert isinstance(row, ImportYearRow)
      row.set_busy(busy)
    for row in self.player_rows.get_components():
      assert isinstance(row, ImportPlayerRow)
      row.set_busy(busy)
    self._update_selection()

  def _reset_preview(self):
    self._workbook = None
    self._years = []
    self.year_rows.items = []
    self.player_rows.items = []
    self.preview_panel.visible = False
    self.review_panel.visible = False
    self._update_selection()

  @handle('workbook_file', 'change')
  @handle('workbook_link', 'change')
  def source_changed(self, **event_args):
    self._reset_preview()
    self.import_status.text = 'Source changed. Preview the workbook before importing.'

  def _preview(self, use_link):
    self._reset_preview()
    self.import_status.text = 'Reading workbook…'
    self._set_busy(True)
    try:
      result = anvil.server.call('preview_historical_workbook',
        None if use_link else self.workbook_file.file,
        self.workbook_link.text if use_link else None)
      if not result['ok']:
        self.import_status.text = result['message']
        return
      self._workbook = result['workbook']
      self._source_url = (self.workbook_link.text or '').strip() if use_link else ''
      self._years = result['years']
      self.year_rows.items = self._years
      self.preview_panel.visible = True
      self.import_status.text = str(len(self._years)) + ' year tabs found. Review courses and names, then select the years to import. Nothing has been saved yet.'
    finally:
      self._set_busy(False)

  @handle('preview_link_button', 'click')
  def preview_link_click(self, **event_args):
    self._preview(True)

  @handle('preview_file_button', 'click')
  def preview_file_click(self, **event_args):
    self._preview(False)

  @handle('select_all_button', 'click')
  def select_all_click(self, **event_args):
    self._capture_years()
    for document in self._years:
      document['selected'] = not document['errors']
    self.year_rows.items = self._years
    self._update_selection()

  @handle('clear_selection_button', 'click')
  def clear_selection_click(self, **event_args):
    self._capture_years()
    for document in self._years:
      document['selected'] = False
    self.year_rows.items = self._years
    self._update_selection()

  @handle('year_rows', 'x-selection-changed')
  def selection_changed(self, **event_args):
    self._capture_years()
    self._update_selection()

  def _show_document(self, document, editable):
    self._capture_players()
    self.review_heading.text = str(document['year']) + ' · ' + document['sheet'] + (' · Preview' if editable else ' · Saved original')
    awards = ['Awards: ' + award['name'] + ' — ' + ', '.join(award['winners']) for award in document['awards']]
    self.review_notes.text = '\n'.join(awards + document['warnings'])
    players = document['players'] if editable else [dict(player) for player in document['players']]
    for player in players:
      player['editable'] = editable
    self.player_rows.items = players
    self.review_panel.visible = True

  @handle('year_rows', 'x-review-year')
  def review_year(self, document, **event_args):
    self._show_document(document, True)

  @handle('close_review_button', 'click')
  def close_review(self, **event_args):
    self._capture_players()
    self.review_panel.visible = False

  @handle('import_years_button', 'click')
  def import_years_click(self, **event_args):
    self._capture_years()
    selections = [
      {'sheet': document['sheet'], 'course': document['course'],
       'names': {str(player['row']): player['name'] for player in document['players']}}
      for document in self._years if document['selected'] and not document['errors']
    ]
    if not selections or self._workbook is None:
      self.import_status.text = 'Preview a workbook and select at least one year first.'
      return
    self._set_busy(True)
    try:
      result = anvil.server.call('import_historical_workbook', self._workbook, selections, self._source_url)
      if not result['ok']:
        self.import_status.text = result['message']
        return
      counts = result['counts']
      self.import_status.text = (
        'Finished years ' + ', '.join(str(year) for year in result['years']) + '. '
        + str(counts['tournaments']) + ' new tournaments, ' + str(counts['entries'])
        + ' new entries, ' + str(counts['awards']) + ' new award records. '
        + 'Matching records were kept without duplicates. Original results are saved below.'
      )
      self.app._load_players()
      self.app._load_events()
      self.app._show_view('imports')
    finally:
      self._set_busy(False)

  @handle('import_history', 'x-view-source')
  def view_saved_source(self, record, **event_args):
    result = anvil.server.call('get_historical_import_source', record)
    if not result['ok']:
      self.import_status.text = result['message']
      return
    self._show_document(result['data'], False)

  @handle('import_history', 'x-open-tournament')
  def open_imported_tournament(self, tournament, **event_args):
    if tournament is not None:
      self.app._creating_tournament = False
      self.app._load_events(selected=tournament)
      self.app._show_view('event')
