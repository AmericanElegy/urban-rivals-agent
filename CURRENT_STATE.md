# Urban Rivals agent current state

Updated 2026-11-11. Owner: James / AmericanElegy. Live checkout is this folder;
there is no dependency on a FantasyBrief checkout for running this project.
Private GitHub repository: https://github.com/AmericanElegy/urban-rivals-agent

## Latest checkpoint

Eighteen exact card evolutions; prior board replay passed 764/764 checks.
The paired extension successfully captured a canvas. The subsequent execution
attempt was stopped by Computer Use because it could not verify the browser URL;
the execution bridge was shut down. No automatic live round is confirmed.
Pairing is resolved; older pairing/server-running notes below are historical.

Execution now requires two consecutive matching public board readings, within
20 seconds, before card selection. Timer changes are excluded; missing or changed
boards reset the candidate. Inspect capture remains a single frame.
The saved stake panel exposed another OCR defect: white-only numeric extraction
could not read purple attack or pink damage. Dedicated color masks now read its
attack 9 and damage 5 with the existing two-read confidence requirement.
This is one recorded panel, not validation across all values or live inputs.
Full-match validation and untimed browser targeting verification remain pending.

## Goal and authority

Build an automatic browser player inspired by Oset's thesis. James selected the
browser and Training Bot first, subsequently permitting Tourney or AI matches.
Verify Tourney's timer before testing it. EFC is not authorized. James also
authorized keeping this project on GitHub for continuity; default to private.
No discretionary paid model call is authorized or required.

## Implemented

- Immutable supported-subset simulator and one-round mixed-strategy matrix solver.
- Expanded mechanics for the eight card evolutions observed in the first training
  board. Exact catalog is `urban_rivals/data/training_cards.json`.
- Local RapidOCR CPU reader, card/evolution checks, board resource extraction,
  public lead recognition, round-to-round engine reconciliation and action phases.
- Opt-in Chrome MV3 extension with local authenticated OCR bridge. Inspect is the
  default. Execution needs both the server flag and the popup checkbox. Live
  driver currently disables its own Fury and does not requeue.
- Scoped URL/frame checks, stale-action rejection, one confirmation attempt per
  round, unknown-card stop, focus-loss stop, Escape/Stop, 15-minute run limit.
- Isolated `.venv` with OCR dependencies and PowerShell install/start commands.
- CI definition for Python unit and Node bridge-policy checks.

## Evidence and limitations

48 Python tests passed, including real authenticated loopback bridge requests,
wrong-origin/unauthorized rejection and duplicate-frame rejection. Six Node
policy/worker tests pass, including popup-started one-frame capture with an
unfocused parent window and no debugger/input calls. Local ONNX OCR correctly read a synthetic round/turn/timer
banner. These checks are NOT real screen-recognition or game-strength evidence.
Offline replay of the first two publicly observed calibration rounds matches
the visible life and pillz receipts (Randal/Taurite, then Bennie/Dr Web Ld).
This does not attribute those rounds to the automatic driver.

James confirmed the extension is installed and supplied screenshots of the paired
popup. Its original startup text was misleading: it said Playing when the server
was still inspect-only. No extension frame had reached the server. Version 0.2.1
adds authenticated mode checking, live progress/error status and bounded waits.
Inspect capture now uses visible-tab pixels, without attaching the debugger, and
stops after saving one frame. Offline `inspect` has no game-turn deadline.

The inspect-only bridge is running on 127.0.0.1:8876, restarted with the existing
local pairing token retained. James reloaded 0.2.1 and reported "Game tab lost
focus or navigated; stopped" with automatic play unchecked. Its window focus
check was incorrectly shared by diagnostics and execution. Version 0.2.2 allows
one-frame inspect capture while the popup/another window holds focus, provided
the exact game tab is still selected in its own window. Live clicks still
require foreground focus; both modes still reject navigation/tab changes.
The popup now states the actual diagnostic workflow and shows its version.
James reloaded 0.2.2. A local /ready check verified that the on-disk token matched
the running server after a reported invalid-token error. Replacing the popup's
token resolved it. The first actual extension capture succeeded: receipt has
action null, stop true, sequence 1. The 332,838-byte canvas PNG shows the Training
menu, correctly cropped without the extension popup. Preserved locally as
`local/first-extension-capture.png`; offline diagnostics classify `training_menu`
and do not invent card records. The real capture transport is now verified.
A second successful extension capture contains the full round-1 Montana/Bangers
board (receipt again action null, stop true). Preserved as
`local/first-board-capture.png` and analyzed in `local/first-board-diagnostics.json`.
The crop excludes the popup and includes the whole board. Offline OCR identifies
the phase and round correctly and reads most names/stats, but Doug Snop's power,
Mendossa's power, Waller's stats and Dr Elisa's raised title still have recognition
errors. Keep those uncertain; do not present recording-frame OCR success as proof
that every live capture is readable. No more setup or transport proof is needed.
The separate inspect-only-server rejection with automatic play checked is
intentional and confirmed in James's second screenshot.

James supplied `C:\Users\James\OneDrive\Desktop\Recording 2026-11-11 054927.mp4`
(73.47 seconds). Six frames were extracted locally under `local/recording/`.
The round-1 frame is saved there as `round1-canvas.png`; offline diagnostics read
the banner, day marker, stats and most names. Numeric preprocessing and direct
high-confidence recognition fixed previously missing standalone digits. Raised
opponent titles now use a separate crop, rejecting stray single letters/digits.
The source media, crops, token and diagnostics are ignored and were not uploaded.

New hands expose unresolved mechanics/cards: Fixit (Protection), Pacarezza
(Damage Exchange), Caballine (Copy), plus Austin/Barcius/Buford/Lucien (Tune Out
and Bet), among others. Do not turn those into supported catalog entries by
dropping their effects. Keep them stopped until current semantics are verified.
No full live match has been validated or attributed to the program. Pixel crop
coordinates and the card catalog were transcribed from the earlier visible
training board, and need verification on captures from the installed extension.
Recognition intentionally stops instead of guessing. The eight-entry catalog is
not a general card database. Many abilities remain unsupported.

## Next step

Continue supported-effect/catalog implementation and board OCR work offline
before enabling automatic input. The one-frame transport works; do not ask
James to repeat pairing, reload or start matches to prove that same fact.
Use the supplied recording for continued diagnostics instead of repeatedly
asking James to start timed matches. The latest screenshot adds Doug Snop,
Joy, Dr Elisa, Mendossa, Orenichi and a partly obscured fourth Montana card.
The unchecked popup can retain a previous checked-mode error until Start is
clicked again; that message alone is not a fresh capture failure.
Do not use Codex's
browser debugger on the same tab while this extension controls it.

If installation is blocked by browser policy, do not bypass it. Report that exact
blocker and use an allowed alternative after discussing it with James.

## Reuse audit

FantasyBrief canonical architecture/current state and bridge/importer code were
inspected read-only. Reusable patterns: source allowlists, timestamped snapshots,
local bridge and stop-on-disconnect. No reusable game OCR was found in those
inspected paths. No FantasyBrief files, production state or schedules changed.

An initial global OCR install selected NumPy 2 and conflicted with nfl-data-py.
The global environment was corrected to NumPy 1.26.4 / OpenCV 4.11.0.86; `pip
check` reports no broken requirements. Bot OCR dependencies now live in `.venv`.
No FantasyBrief pipeline was run as a verification step.

## Source facts

Official support says the legacy public API is discontinued and a replacement
is planned. The thesis's API address is historical, not a setup step. Use official
card/rules pages and visible game data. Source links and setup are in README.md.


## Offline OCR repair, 2026-11-11

James authorized the proposed OCR work. No new match, pairing, extension reload,
API access or paid call is needed. Work uses the existing full-board extension
capture and supplied recording only. The running bridge remains inspect-only;
restart is unnecessary for offline replay and it has not loaded these changes.

Added `tests/fixtures/ocr_replay.json`, `urban_rivals/replay.py` and the `replay`
CLI. Seven labeled source frames produce eleven cases including resampling at
85%/115%, rounds 1–3, menus, stake and result. Labels are checked in; all source
media and detailed reports remain ignored in local/. Resampling is not proof
of responsive layouts or different browser geometry.

Changes: wider stat crops avoid clipping selected digits; threshold/component
filtering removes colored icons and border fragments; digit consensus abstains
on disagreement. Title OCR groups the top text line, avoiding art lettering.
A white selection disc distinguishes a revealed lead from a hover enlargement.
The isolated move clock rejects invalid seconds and world-clock/banner noise.
Purple/yellow pill markers separately identify played cards; unreadable counts
are explicit errors and prevent recognition_complete/live actions. Dimmed base
stats are retained from the verified initial hand, not guessed from dim pixels.
Unknown abilities/catalog entries still block execution.

44 Python tests, six Node tests and the one-game simulator smoke check pass.
The real-image replay is separate from these unit checks. Remaining work is
small-font digit/count recognition and reducing first-board processing latency;
no live match or automatic input has been validated. Keep live input disabled.

Latest OCR continuation: all original 375 checks pass. Expanded replay now
passes 639/639 fields over seventeen cases, including additional resampling of
rounds 1–3; zero unreadable or incorrect values. Board diagnostics now take
2.2–5.3 seconds after profiling and detector-size changes, versus 9.6–13.4 before.
Narrow glyph padding and a dedicated padded counter crop resolve the five old
failures without lowering confidence thresholds. Diagnostics/live perception
share the counter routine. Detailed detector settings restore after exceptions.
48 Python tests, six Node tests and simulator smoke check pass. Exact scope and
limits are in `OCR_STATUS.md`; detailed ignored report is
`local/ocr-replay-report.json`. The local replay now exits 0.

Next: unsupported ability/catalog implementation and full live input/receipt
validation. No new match or input was attempted; the running bridge remains on
the prior inspect-only process. No hand cache was added because measured OCR
work alone delivered the speed improvement. Treat all older OCR-failure notes
above as historical; this paragraph and OCR_STATUS.md describe current evidence.


## Mechanics continuation, 2026-11-11

Current evidence supersedes the earlier eight-card/unsupported recording-hand
notes above. Catalog: eighteen exact evolutions. Added Doug Snop, Joy, Fixit 4*,
Pacarezza 2*, Orenichi, Waller, Austin 5*, Barcius 3*, Buford 3* and Lucien 4*.
Protection Power/Damage, conditional Exchange, Tune Out and Bet are implemented.
Current official card definitions were read via existing signed-in Chrome, with
public source links and limitations in MECHANICS_STATUS.md. Temporary research
tabs were closed; the original collection tab, decks and game client were not
changed. No authentication/session data was saved or uploaded.

The engine matches three completed recorded rounds, and the real live board
reader reconciles four sequential native boards through the start of round 4.
New command: `python -m urban_rivals verify-match tests/fixtures/recorded_match.json`.
An offline advice example is examples/recorded_training.json (respond with
--observed-card 0). These are recording checks, not a completed automatic match.

Expanded OCR corpus: 764/764 fields across twenty cases, including a new stable
round-4 frame and readiness checks. All recording-hand cases are engine_ready;
Montana remains blocked on Dr Elisa/Mendossa. Native sequence report stays in
local/match-verification.json. Latest 20-case diagnostic timings: 3.0–7.1 seconds;
extra resampled counter fallbacks make this broader run slower than the previous
17-case measurement. Do not claim a live end-to-end latency guarantee.

71 Python tests, six Node tests, existing two older round receipts, three newly
reconciled round receipts and simulator/advice checks pass. Simultaneous same-stat
Exchange, Copy, persistent effects, Stop Bonus and Protection Ability/Bonus still
fail closed. Fury/Tune Out has unit coverage but no supplied Fury-round receipt.
Fixit/Pacarezza's active effects have rule-based tests, not isolated live receipts.
The local bridge was refreshed with --reuse-pairing-token, execution remains
disabled, and authenticated readiness passed. No extension reload or pairing
change is needed. Next work
is bounded Training Bot action-panel/input validation on an idle supported match,
then full live round receipts. Do not interfere with an active game or infer a
complete match from the fourth round's intermediate animation.


Live calibration was explicitly authorized by James. Preparation and the current
pairing blocker are recorded in LIVE_CALIBRATION.md. No timed match has started.
A phase-hint timing repair and explicit PowerShell token-reuse switch are ready;
72 Python tests and launcher syntax validation pass. Resume live calibration
after the user's local pairing step; do not repeat an authorization question.
