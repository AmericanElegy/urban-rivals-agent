# Urban Rivals agent current state

Updated 2026-11-11. Owner: James / AmericanElegy. Live checkout is this folder;
there is no dependency on a FantasyBrief checkout for running this project.
Private GitHub repository: https://github.com/AmericanElegy/urban-rivals-agent

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

38 Python tests passed, including real authenticated loopback bridge requests,
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
James needs to reload 0.2.2 once; actual new transport validation is pending.
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

James reloads the installed extension to 0.2.2 and takes one inspect-only frame.
Then validate the saved canvas, OCR crops and evolution recognition offline
before enabling any automatic input. Use the supplied recording for continued
diagnostics instead of repeatedly asking James to start timed matches.
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
