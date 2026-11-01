"""Start here when finding code in the Anvil Editor.

APP ENTRY POINTS
  Form1                  Committee dashboard: login, navigation, tournament selection.
  PublicStandings        Public news, standings, tee times and participant balances.

COMMITTEE PAGE FORMS (expand the Pages package)
  Pages.TournamentDetails     Tournament details, creation and participant entries.
  Pages.TournamentField       Divisions, Rattlercaps, filtering and player selection.
  Pages.ParticipantDirectory  Roster search, individual entry, CSV import and editing.
  Pages.RoundOne             Foursomes, tee times and first-round scores.
  Pages.RoundTwo             Pair previews, assignments and shared scores.
  Pages.Standings            Overall/division leaderboards and sorting.
  Pages.Expenses             Expense categories, assignments and payments.
  Pages.EmailParticipants    Recipient filters, CSV export and email composition.
  Pages.NewsEditor           Create, edit and publish tournament news.

REUSABLE FORMS (expand the Components package)
  Components.Tournament      EntryDetailsRow and EntryPlayerChoice.
  Components.Participants    PlayerRow.
  Components.Scoring         FoursomeRow, RoundTwoPairingRow, StandingRow and
                             the existing individual score/card row Forms.
  Components.Budget          Expense category, participant, payment and detail rows.
  Components.Public          PublicTournamentStandings, NewsPostCard and public rows.

SHARED LAYOUT AND SERVER
  Layouts.BaseLayout         Page frame and mobile navigation.
  Theme > Assets > theme.css Shared appearance.
  Server Modules > Tracker   Server calls, permissions and Data Table operations.

HOW PAGES FIT TOGETHER
  Each page owns its HTML, controls, handlers, filters and unsaved edits.
  Form1 creates the pages from its template, then calls initialize(self) on them.
  A page's app attribute points to Form1 for the selected tournament, roster,
  divisions and cross-page refreshes. Form1._load_event_data coordinates loading;
  the page's load/clear methods handle that page's controls.
  Navigation changes visibility and keeps the same page instances alive.
  RepeatingPanel item templates send their existing events to their owning page.
  Server callable names and Data Table definitions are unchanged.
"""
