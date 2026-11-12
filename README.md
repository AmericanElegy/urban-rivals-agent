# Urban Rivals agent

Local Python implementation inspired by Marcelina Oset's 2024 thesis,
*Developing an AI Agent for the Urban Rivals Card Game*. The thesis is reference
material, not a complete source distribution. This repository is new code.

## Run now

Python 3.11 or later; the engine has no third-party dependencies.
First change to the project directory. Copy this entire block into PowerShell
(including `Set-Location`); it also works when PowerShell starts in your home folder:

```powershell
Set-Location -LiteralPath 'C:\Users\James\OneDrive\Documents\ChatGPT\urban-rivals bot'
python -m urban_rivals advise examples/basic.json
python -m urban_rivals simulate examples/basic.json --games 5 --iterations 1000
python -m unittest discover -s tests -v
```

If Python reports `No module named urban_rivals`, check that `Get-Location`
shows the project directory above. The commands use the local source directly;
no package installation or API access is required.

`advise` prints a mixed strategy, a sampled move, a heuristic score, and the
equilibrium gap in score units. Card indices are zero-based. `pillz` means **paid**
pillz; attack includes one additional free pill. Fury costs three additional pillz.
When responding, supply `--side 1 --observed-card 0` if side 0 leads card 0.

The example contains invented cards, not a current card database. Edit a copy
under `local/` to analyze another hand. Starting life and pillz are configurable
per player. Never infer a game mode's starting life from the example.

## What works

- Immutable game states, legal moves, automatic local match simulation.
- Free pill, Fury, attack ties by stars then initiative, damage and KO.
- Same-clan bonus activation counted from the original hand, including used cards.
- Basic power, damage, attack, life and pillz modifiers, with min/max bounds.
- Courage, Reprisal, Confidence, Revenge, Defeat and Victory Or Defeat conditions.
- Stop Opp. Ability, compound modifiers, Day/Night (requires an observation),
  Unison/Disunion, Symmetry/Asymmetry, Support/Brawl, Growth/Degrowth and Equalizer.
- Power/Damage Protection and Exchange, Tune Out, and strict Bet conditions
  (with unverified combinations still rejected; see MECHANICS_STATUS.md).
- Approximate zero-sum mixed strategies via averaged regret matching.
- Public lead-card choice is separated from hidden pillz and Fury bidding.
- A local OCR reader and Chrome bridge, with separate inspect and execute modes,
  fresh-frame checks, verified pillz increments and no automatic requeue.
- A transport-independent turn controller and a canvas-specific action state
  machine, tested locally. Live game validation is still pending.

## Current limits

**The browser driver is implemented but not live-validated.** The Unity WebGL
client exposes a canvas rather than card/button DOM elements. OCR crop positions,
star counting and selected-card detection pass the saved-capture regression set.
Input coordinates and full live action/receipt handling still need validation. Do not treat passing mocked
control tests or the synthetic OCR test as a completed live match.

The catalog covers 26 specific card evolutions from the saved training
boards and recording. The first input profile supports the cataloged Bangers cards in
our hand; the other entries cover the observed opponents. Other cards/evolutions stop recognition. The GhosTown entries are
Day-only until their Night behavior is cataloged. The first live driver uses no
Fury; the simulator still models Fury. It plays the current manually opened
Training Bot match only. It does not log in or automatically queue another match.

Search currently looks one round ahead using a hand/resource heuristic for
continuation. On the final round it evaluates the match outcome. The gap measures
the current matrix solver's convergence, not match win probability or the error
in the continuation heuristic. Sampling a mixed strategy matters: always selecting
its most likely move makes play predictable.

Supported mechanics include Stop Ability/Bonus, Power/Damage Protection and
Exchange, Power/Damage cancellation, and Attack Per Opp. Power/Damage. See
MECHANICS_STATUS.md for exact scope and rejection boundaries. Unsupported effect
text raises an error, including recursive/conditional ability copy, stat Copy, Protection Ability/Bonus, poison and
regeneration, recovery, Oculus and Leader mechanics. Nested conditions and many
modern keywords are not implemented. Do not remove
unsupported effects to make a real hand load: that would produce incorrect advice.
Effect ordering for the supported subset still needs comparison with live logs.
No random attack mode is modeled. No ranking, format legality or deck checking is
implemented. The random simulation opponent is a smoke test, not a performance
benchmark. No claim of improved playing strength has been established.

## Design improvements over the thesis approach

The thesis's minimax gives an adversary knowledge of hidden pillz. Its alternative
averages over pillz assignments rather than solving strategic hidden bidding.
This implementation constructs a payoff matrix for each public lead card and
solves for both players' mixed bids. The responder's strategy cannot depend on
the leader's hidden bid. This is a modeling improvement; playing strength needs
separate testing and deeper search.

Python integers also avoid the thesis snippets' narrow integer attack overflow.
Unknown abilities are rejected instead of silently omitted. State transitions
do not mutate the shared card definitions.

## Browser target agreed with James

Browser WebGL version, **Training Bot first**. James also authorized Tourney tests;
its move timer must be verified first. EFC is outside current live-test
scope. The current driver deliberately allows training only. Use the existing signed-in Chrome session; never store passwords or export
session cookies. Live calibration must wait while James is playing a match.

Next implementation milestones:

1. Capture Training Bot board, selected-card and bidding screens at known canvas
   dimensions; establish recognition confidence and game-state reconciliation.
2. Obtain current card text/stats through official card pages; add the mechanics
   present in both training hands. The legacy public API is discontinued; do not
   make its developer link or API-key registration a setup requirement.
3. Implement verified card selection, pillz/Fury selection, submission and result
   recognition; stop on ambiguity, login screens or state mismatch.
4. Complete and reconcile a full Training Bot match, then test repeated matches
   with bounded runtime, a stop control and local receipts.
5. Add bounded deeper search, caching and measured policy comparisons.

Live inspection on 2026-11-11 reached a Training Bot board (Smash Jabber, 15 life,
12 pillz initially) and the selected-card stake panel. The panel exposes minus,
plus, minimum, maximum, Fury and confirmation controls visually, not through DOM.
Training showed about two minutes per turn. Human input was detected during
calibration, and some turns advanced without a verified submission by this agent.
No complete match is attributed to the program, and there is no live win-rate
claim. The last observed browser screen was the game home screen.

The actual hand contained Stop Opp. Ability, Brawl, compound Power And Damage,
Day, Unison and Asymmetry effects. These now have implementation and unit checks,
but their live round reconciliation is pending. The invented demonstration hand
is still not evidence of live strength.

## Local OCR and browser bridge setup

This uses **local screenshot recognition**, not the discontinued game API and
not a conventional accessibility screen reader. No paid model/provider call is
made. RapidOCR's packaged ONNX models run on the CPU. The dedicated `.venv`
isolates its dependencies from FantasyBrief.

```powershell
Set-Location -LiteralPath 'C:\Users\James\OneDrive\Documents\ChatGPT\urban-rivals bot'
.\Install-TrainingAgent.ps1
.\Start-TrainingAgent.ps1
```

The OCR environment is already installed on the current desktop. Reinstallation
is needed only on a fresh checkout/machine. The starter defaults to **inspect
only**, saves a temporary pairing token to `local/pairing-token.txt`, and listens on `127.0.0.1:8876`.
Leave that PowerShell window open. Ctrl+C stops the bridge.

Load `browser-extension/` as an unpacked Chrome extension. In `chrome://extensions`,
turn on Developer mode if available, choose Load unpacked, and select this
project's `browser-extension` folder. If a browser policy blocks installation,
stop there; do not bypass the policy. This extension is separate from the existing
FantasyBrief extension and changes none of its permissions or sources.

The extension requests `activeTab`, `scripting`, `debugger` and access to the
local loopback bridge. Chrome's debugger permission is broad; this code restricts
it to the exact official WebGL game URL and the tab explicitly started by the
user. Inspect mode uses visible-tab capture without attaching the debugger.
Execution mode uses the debugger connection for mouse inputs. It
does not read cookies, passwords, hidden game memory or private game API traffic.
The pairing token stays in extension memory for the run, not persistent storage.

1. Open the signed-in browser game and keep the full canvas visible. Any board
   is useful for diagnostics. Only automatic play requires a fresh **Training
   Bot** match at round 1 before any card is selected.
2. Close DevTools and end any other debugger control of that tab (including Codex
   browser control) before starting the extension; two debuggers may conflict.
3. Open `local/pairing-token.txt`, copy its contents into the extension popup's
   token field, leave automatic play **unchecked**, and click Start. Inspect
   mode captures one frame and stops; there is no ongoing diagnostic match loop.
4. Analyze `local/latest-canvas.png` without a turn deadline:

   ```powershell
   .\.venv\Scripts\python.exe -m urban_rivals inspect local/latest-canvas.png
   ```

   `local/receipts.jsonl` records capture status. The offline reader checks every
   crop independently and reports unknown names and unreadable stats. Captures
   and reports are local, ignored by Git, and never sent to GitHub.
5. Only after real OCR/input calibration, restart the server with
   `.\Start-TrainingAgent.ps1 -Execute -ReusePairingToken`, start a fresh match, and explicitly check
   automatic play in the extension. Both switches are required for clicks.
6. Press Escape in the game or Stop in the popup to end control. Focus loss,
   navigation, stale observations, unknown cards, engine/receipt disagreement and
   a 15-minute session limit also stop it. No input is automatically retried after
   an uncertain outcome. No automatic requeue is implemented.

`local/latest-canvas.png` is overwritten by each capture; `local/receipts.jsonl`
holds action/status receipts. The image contains the game canvas only. The bridge
requires a random pairing token, rejects website origins, and binds to loopback.
Restarting the bridge normally rotates the token. `serve --reuse-pairing-token`
retains it for an explicit diagnostic restart. Never expose its port to the network.

## Reused FantasyBrief patterns

Reviewed `C:\FantasyBrief\browser-extensions\draftsharks-bridge` and the visible
transcript importer read-only. Their DOM readers cannot read a Unity canvas.
This project adapts their architecture: exact source allowlists, versioned
observations, explicit freshness, local bridging and stop-on-disconnect behavior.
It does not import FantasyBrief runtime state, credentials, paid-provider code,
schedules or production dependencies. No FantasyBrief files were modified.

## Sources

- Supplied thesis: `C:\Users\James\OneDrive\Desktop\Oset2024DevelopingAnAI.pdf`,
  especially sections 3.3-3.5 and chapter 5.
- Official rules: https://www.urban-rivals.com/game/rules/ (checked 2026-11-11).
  Current examples confirm the free pill, Fury cost, and bonus activation.
- API status: https://www.urban-rivals.com/support/ under "Press, partnerships
  and the fansite API" says the legacy public API is discontinued and a new API
  is planned. Checked 2026-11-11. The thesis's `/api/developer/` address is a
  historical reference, not a working setup step. No API access is required for
  this project's current local commands; no API credentials have been used.

The official rules differ from the thesis in places, such as Protection versus
Cancel. Unsupported mechanics must be checked against current sources before
implementation. Do not assume 2024 card data or mode rules are current.


## Offline OCR regression replay

Run the labeled replay from this checkout with the OCR virtual environment:

```powershell
.\.venv\Scripts\python.exe -m urban_rivals replay tests/fixtures/ocr_replay.json
```

The manifest contains manually checked labels for the saved extension board,
recording rounds 1–3, training menu, stake panel and match result. Source PNGs
stay in ignored `local/`; missing images are reported as missing, never passed.
The report at `local/ocr-replay-report.json` separates incorrect values from
unreadable fields and records per-frame processing time. Resampling at 85% and
115% tests image degradation, not arbitrary browser layouts. Played cards are
checked for identity and paid pillz; their dimmed base stats must be retained
from a verified initial hand rather than inferred anew.

OCR uses local CPU inference only. Recognition scores are not calibrated
probabilities. Unsupported catalog entries still block execution even if their
visible text and stats can be read. Replay success is separate from live input
validation and move speed.


Latest local OCR validation: **764/764 fields pass across 20 cases**, with board
diagnostics approximately 3.0–7.1 seconds in this broader run. See [OCR_STATUS.md](OCR_STATUS.md) for
exact coverage and remaining live-play blockers. These results do not establish
support for unknown abilities or authorize automatic input from an unsupported
hand. Source media remains local; GitHub CI runs the portable tests only.


## Recorded-match verification

```powershell
.\.venv\Scripts\python.exe -m urban_rivals verify-match tests/fixtures/recorded_match.json
.\.venv\Scripts\python.exe -m urban_rivals advise examples/recorded_training.json --observed-card 0 --iterations 100
```

The first command exercises the live board reader against four saved native
boards, including real round-to-round engine/resource reconciliation. It stops
on any missing source, recognition failure or mismatched expected receipt. The
second analyzes the recorded opening hand offline. Neither command clicks or
queues a game. Full scope and current official sources: [MECHANICS_STATUS.md](MECHANICS_STATUS.md).


Additional local verification:

```powershell
python -m urban_rivals verify-log tests/fixtures/live_copy_battle_log.json
python -m urban_rivals replay tests/fixtures/stake_panels.json --output local/panel-replay
```

Extension 0.2.3 keeps pairing in memory for the browser session (requires one
reload after adding its storage permission). Start still works if an older
loaded manifest lacks storage. Reopening the popup defaults automatic play off.
The button and completion status distinguish one-frame inspection from automatic
play. Restart the bridge after engine changes; retain the token with
-ReusePairingToken. See CURRENT_STATE.md and LIVE_CALIBRATION.md before live tests.
