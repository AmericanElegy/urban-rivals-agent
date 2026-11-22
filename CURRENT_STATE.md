# Urban Rivals agent current state

Updated 2026-11-22. Owner: James / AmericanElegy.
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
- 1,726 exact evolutions / 1,723 names in urban_rivals/data/training_cards.json.
  Public source corpus: 2,507 maximum-level cards across all 36 official clans.
  Unsupported effects and conflicting evolution data are quarantined.
- Added source-preserving Copy Opp. Ability/Bonus, printed Power/Damage Copy,
  Stop Bonus, Power/Damage/Attack Cancel, Protection Ability/Bonus/Attack,
  fractional Pillz recovery, and Attack scaling from opposing stats or starting
  Life/Pillz. Recursive/conditional copy and uncertain
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
- Extension 0.2.4 remembers token in chrome.storage.session only. Old loaded
  manifests without storage no longer crash Start. Execution checkbox stays
  off when reopening. Inspect completion explicitly says automatic play is OFF.
- Bridge readiness exposes engine revision and logs requested mode without
  token data. Extension rejects old engines before input and explains missing
  bridge/debugger conflicts. Inspect capture no longer needs a card catalog.

## Actual evidence

154 Python tests and 15 extension tests pass. Fresh Oblivion-board replay passes
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

The latest execution attempt reached authenticated /ready but produced no
execution frame. Physical Escape stopped Computer Use, and the execution bridge
was shut down. A later Failed to fetch report followed that shutdown. The bridge
has now been restored and authenticated in INSPECT ONLY mode with the same token
and engine_revision copy-v1. No live automatic input is confirmed. Native input
can restore Chrome to half-width; avoid disturbing the user's active game.

Before a bounded live test: verify /ready execution mode and engine_revision,
fully visible canvas, a single debugger controller, and AUTO waiting status
before Training PLAY. Native screen observation can coexist with the extension;
ChatGPT browser debugging on the game tab cannot. Stop on unknown cards, stale
frames, uncertain readings or mismatching receipts. Restore inspect afterward.

All media, tokens, local receipts and pairing files remain ignored under local/.
OCR uses this checkout's .venv; do not change FantasyBrief's environment.
The legacy game API is discontinued; current commands need no game API key.

## Focus-pause calibration update

The previous startup stop was Chrome losing focus while James reported status.
Version 0.2.4 now pauses only at a frame boundary for up to 60 seconds, without
capture or input while unfocused. Tab/navigation changes still stop; focus lost
during recognition discards a pending click and stops. Resuming sets a validated
focus_resumed flag and clears board/panel stability candidates without losing
pending submission history. Unit tests cover pause/resume and mid-OCR focus loss.
Popup local validation errors now remain visible instead of being overwritten
by Not started during status polling.

James reloaded 0.2.4 and confirmed PAUSED status. Bridge process was started
execution-enabled with the existing token and copy-v1 engine. He was instructed
to return to Chrome, wait for AUTO waiting, then Training PLAY without replying
here. Monitor receipts; do not restart or run OCR replays during this attempt.
One earlier execution frame reached the menu and returned no action, then its
HTTP client disconnected (WinError 10053). No gameplay input is confirmed yet.

## Latest catalog and animation checkpoint (2026-11-12)

Live run reached a board but stopped before input on unknown Chlora. A manual
restart during a card flip obscured the round banner. Unknown names still stop;
a temporarily unreadable round/timer now waits with no action. Known clocks
under 12 seconds still stop. The saved flip frame returns wait in 4.16 seconds.

Chlora, Dixie, Jenny, Kreenk Ld, Lord Oon Ld, Kati, Yang Luhan and Yoshito were
verified against official card pages. Damage Copy uses printed opposing damage
before bonuses/Fury; own Fury applies afterward. Matching Exchange takes
precedence, and Stop/Cancel remove the appropriate copy. Attack Cancel removes
opposing attack modifiers but preserves the attack from paid/free pillz.

All 2,507 rendered maximum-level card facts from 36 official clan pages were
collected, with per-clan row counts checked against visible headings. Audit data
contains only card facts and official source URLs, not prices, holdings, account
identifiers or images. Import accepted supported mechanics only; 788 source
records are rejected. Current catalog has 1,726 evolutions / 1,723 names.
GhosTown, Leader and Oculus bulk imports remain excluded for their special rules.
Seeded GhosTown Day-only entries remain unchanged.

Live first-hand recognition now selects exact (name,power,damage,stars), then
retains the verified immutable evolution through later rounds. Name-only replay
manifests retain their original reference evolution. Four-star Fixit (Reprisal
Protection) and five-star Fixit (always Protection) are separate entries.

154 Python tests and 15 extension tests pass. Four saved board checkpoints and
all four completed Oblivion-log rounds remain consistent. Import is idempotent;
unsupported/conflicting effects are not silently omitted. Automatic live
selection/stake/confirmation remains unverified. James has left the game on the
untimed Training menu for a controlled retry; refresh the old bridge process
once to load these changes before Start. Do not run competing OCR while armed.

## Wide-layout and focus checkpoint (2026-11-12)

The last reported run stopped after 60 seconds without Chrome focus. Automatic
startup now closes its popup after connection, returning focus to the game.
Inspection and failed startup keep the popup visible. No focus guards are removed.

HUD crops now follow CSS canvas width and edge/center anchors. A narrower card
stat crop removes a bright border that appeared as a leading digit. Original
OCR replay passes 764/764 fields; wide-layout replay passes 159/159 fields at
three scales. The wide untouched board also passes full state/evolution
verification in 5.842 seconds. These are offline results, not proven live input.
Combined Power And Damage Cancel expands into both existing cancel effects;
14 additional official card evolutions passed strict import.

117 Python tests and 15 extension tests pass. Keep the current token; refresh
the bridge once before the next automatic test to load these HUD changes.
No automatic card selection, stake confirmation or completed match is proven.

### Retained HUD follow-up

Run 350c0d31-5d26-4c0a-8430-1a2e91f656f9 connected and captured a real
round-1 board repeatedly, but issued no actions. Stopped explicitly via /stop.
The client retained reference HUD positions despite a larger CSS canvas;
width-derived timer crop returned incomplete 01:. A complete reference timer
now selects that known layout when the width-derived timer is unreadable.
Saved frame reads 103 seconds and all four resources correctly (15/15,12/12).
Wide OCR replay remains 159/159; 118 Python tests pass.
The same frame's raised Dark Morlha damage remains unreadable, and unsupported
mechanics are not enabled. No live selection or completed automatic match.
Geometry is now saved locally beside latest-canvas.png for diagnosis.
Bridge is being restored inspect-only while the user finishes manually.

Retained-HUD fix regression: original 764/764 and wide 159/159 pass. James confirmed menu ready; latest bridge restarted execution-enabled as process 34072 with unchanged token for one fresh match. No competing OCR while armed.

## Coverage distinction and Dr Saw follow-up

Run a91dc449-204f-47f0-a841-4361496e3ff5 got past the timer read, then
stopped on Dr Saw before input. The source facts existed; +1 Life Per Damage
was not implemented. Official rules at https://www.urban-rivals.com/game/rules/
Pillz/Life per Damage describe recovery from damage, including Fury. Added
positive Life/Pillz per-damage victory effects after final damage calculation,
with reduction, Fury, loss, Stop Ability, zero-damage and invalid-variant tests.
122 Python tests pass. Strict reimport adds 41 evolutions: 1,392 accepted source
records, 1,115 rejected, 1,399 catalog evolutions / 1,396 names.

Full saved-hand diagnostics now parse seven cards including Dr Saw; Kersten
remains rejected for Poison 1 Min 1. This is not an OCR/evolution-data gap.
Do not ask James to repeat random live matches for each known engine gap.
Prioritize offline mechanics coverage and full-hand diagnostics before another
live execution test. New `coverage` CLI separates source collection, parsed
records, lower-evolution limits, rejected reasons and unverified live input.

Bridge process 37196 is inspect-only, same token. No live input or completed
automatic match proven. No current automatic run is armed. Public source audit
remains checked in; private saved-frame diagnostics remain ignored locally.

## Official reference reconciliation — 2026-11-22

James directed us to expand the card/level/rule reference first and suggested
checking a wiki/bulk source before individual pages. Public wiki API acquisition
completed 4,025 main-namespace pages in 81 cached batches. Parsed 2,005 card
records / 6,279 level entries; 1,964 names match the 2,507 current official cards.
The GitHub pakoito/CardsFromUrbanRivals dataset was evaluated locally (2,272
single-level records) but not imported because it does not solve evolutions.

Official collection now covers all 2,507 current card pages and 7,930 evolution
rows, preserving per-level abilities, unlock markers, bonus text, visible
explanations and URLs. The strict reconciliation validates every required field,
level sequence, identity and maximum-level official snapshot: 2,507 cards pass,
zero require review, and all 624 recorded wiki conflicts are resolved in favor
of the current official table. Five Day/Night ability pairs and both GhosTown
bonus states are explicitly retained as conditional official variants.
Six accented names damaged in the earlier source import were verified against
card IDs and corrected in the audit and gameplay catalog. No heuristic-only
name changes and no unsupported mechanics enabled.

Checked-in urban_rivals/data/card_reference.json now uses official tables for all
7,930 preferred level records. The separate checked-in
urban_rivals/data/reference_reconciliation.json retains the per-level wiki
comparison: 2,182 cards differ, including 3,777 missing wiki fields, 3,518 field
differences, 1,791 levels added from official pages, and 10 wiki-only levels.
These counts do not prove historical removed-level coverage, mechanics semantics,
or format legality; those remain separate implementation and validation tasks.

Commands: python -m urban_rivals reference "Fixit"; collection/rebuild modules
urban_rivals.wiki_reference and urban_rivals.reference_database. See
REFERENCE_DATABASE.md for provenance and refresh inputs. Reference facts never
enter the execution catalog automatically. Known reference cards rejected by
execution now report the validation/mechanic gap instead of missing card data.

154 Python tests and 15 extension tests pass. Regression verifies official
four-star Fixit 7/6 Reprisal overrides the wiki's older 7/5 entry for lookup.
Live automatic play remains unproven and is not armed. Bridge remains inspect-only
(process 37196 predates reference changes; refresh only when needed). Public
reference is committed; raw wiki pages, private captures and token remain local.

## Offline mechanics expansion — 2026-11-22

After completing the official evolution reconciliation, effect-frequency review
selected four stateless, officially described families before persistent effects.
Implemented source-aware Protection Ability/Bonus plus Attack punctuation,
defeat-based fractional Pillz recovery (floor, minimum one, using the full attack
allocation), Attack Per Life/Pillz Left from pre-move resources, printed Power
Copy, combined printed Power/Damage Copy, and activated Bonus Copy. Copied bonus
effects retain the copier's ability/bonus source; inactive, conditional and
recursive Bonus Copy remain fail-closed.

The idempotent `python -m urban_rivals.catalog_import` refresh re-evaluates all
retained official maximum-level facts after parser changes. These mechanics add
327 supported records: parsed source coverage is now 1,719/2,507, with 788
rejected; the executable catalog is 1,726 evolutions / 1,723 names. This is
offline mechanics coverage, not live validation. Poison/Toxin/Heal/Regen,
Stop/Killshot/After/Versus compound conditions, special clans and ambiguous
cross-source cycles remain rejected.
