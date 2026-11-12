# Urban Rivals agent current state

Updated 2026-11-11. Owner: James / AmericanElegy.
Live checkout: C:\Users\James\OneDrive\Documents\ChatGPT\urban-rivals bot
Private origin: https://github.com/AmericanElegy/urban-rivals-agent

## Goal and working agreement

Build automatic browser play inspired by Oset's thesis; Training Bot first.
James also authorized Tourney tests (verify its timer); EFC is not authorized.
Continue autonomously through research, implementation, tests and calibration;
do not end the turn after each passing test. Ask only for needed user action or
information. No discretionary paid model calls are authorized or needed.

## Current implementation

- Supported-subset immutable engine and one-round mixed-strategy solver.
- 26 exact evolutions in urban_rivals/data/training_cards.json.
- Added source-preserving Copy Opp. Ability, Stop Bonus, Power/Damage Cancel,
  Attack Per Opp. Power/Damage. Recursive/conditional copy and uncertain
  cross-source Stop cycles remain rejected. See MECHANICS_STATUS.md.
- Board recognition validates names, stats, resources, used cards, initiative,
  clock and previous-round receipts. Two matching public states are required
  before card selection; timer changes are excluded.
- Stake reader now uses color-specific digit masks and a tighter name crop
  excluding the clan logo. Two matching panel reads precede each action.
- Exact all-in bids may use MAX once after verified MIN/no-Fury, then verify
  the resulting attack before confirming. This shortcut needs live calibration.
- Local bridge defaults to inspect; execution requires both its flag and popup
  checkbox. No own Fury, login, automatic requeue or unknown-card input.
- Extension 0.2.3 remembers token in chrome.storage.session only. Old loaded
  manifests without storage no longer crash Start. Execution checkbox stays
  off when reopening. Inspect completion explicitly says automatic play is OFF.
- Bridge readiness exposes engine revision and logs requested mode without
  token data. Extension rejects old engines before input and explains missing
  bridge/debugger conflicts. Inspect capture no longer needs a card catalog.

## Actual evidence

100 Python tests and 11 extension tests pass. Fresh Oblivion-board replay passes
147/147 fields at three scales. Four recorded stake panels pass 48/48 fields.
The earlier board regression passed 764/764 fields; four recorded sequential
boards still reconcile three completed rounds.

The first recent Training match was later found completed with a 10-2 victory;
its battle log matches all four rounds under seven possible Fury histories.
Our round-3 Fury is forced by the receipts; opposing Fury/reserves remain
ambiguous. This match is NOT attributed to automatic play. Reproduce with:
python -m urban_rivals verify-log tests/fixtures/live_copy_battle_log.json

The next manual launch drew Mercury Cr, Veronica, Eris and Sol Hona. No execution
frames reached the bridge. All four exact evolutions have since been checked
against official card pages and added. Full automatic live input is unverified.

## Current live setup and next actions

Chrome browser 4, game tab 19121954, official WebGL URL; native Chrome window
6753788. Refresh bindings/coordinates before input. Last observed screen is the
untimed Training setup modal. Research tab 19122069 is disposable.

Pairing works. James loaded extension 0.2.3, reported an error near storage
initialization and then Failed to fetch. Guarding optional session storage fixes
the former; the bridge had been stopped during the unsupported-hand attempt,
explaining its unavailability afterward. A later non-ASCII-header error came
from pasted token text; strict character validation now rejects it before fetch.
James recopied the token and confirmed successful INSPECT capture.

The bridge is now execution-enabled with engine_revision copy-v1 for a bounded
user-started live attempt, same token retained. Native input restores Chrome to
half-width, so James is handling final Start/Training PLAY. Do not restart or run
competing OCR during the attempt. Monitor local receipts; restore inspect after.

Before a bounded live test: verify /ready execution mode and engine_revision,
fully visible canvas, a single debugger controller, and AUTO waiting status
before Training PLAY. Native screen observation can coexist with the extension;
ChatGPT browser debugging on the game tab cannot. Stop on unknown cards, stale
frames, uncertain readings or mismatching receipts. Restore inspect afterward.

All media, tokens, local receipts and pairing files remain ignored under local/.
OCR uses this checkout's .venv; do not change FantasyBrief's environment.
The legacy game API is discontinued; current commands need no game API key.
