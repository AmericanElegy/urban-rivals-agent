# Live calibration preparation — 2026-11-11

Status: not yet started. James explicitly authorized a live Training Bot test.
Browser Chrome 3, existing Urban Rivals tab, is signed in and idle on the Training
modal. No timed match was launched and no bot gameplay click was executed.
The current deck display is Bangers, eight cards, twenty stars, power total 49,
damage total 31. These totals match the intended profile; the actual first hand
still needs verification. Do not substitute a ranked mode.

James reported an invalid pairing token in the popup. The existing file token
successfully authenticates to /ready on 127.0.0.1:8876 and the server reports
inspect-only. Popup pairing remains pending. The question sent to James asks him
to copy the file with Get-Content -Raw ... | Set-Clipboard, replace the entire
password field, keep automatic play unchecked, and inspect-capture the menu.
The nonce must not be put in chat or Git. No token has been rotated.

Browser security rejected a chrome://newtab step for automatic transfer because
only HTTP/HTTPS protocols are allowed. Do not work around that denial with a
local file URL, browser commands or another browser surface. James must perform
the local copy/paste step. Native Chrome controls also encountered stale bounds
and focus changes; rebind fresh returned windows and screenshot geometry before
any UI input. The last Chrome window was half-width: maximize before calibration
so the canvas is not undersampled. Do not use stale coordinates.

Independent timing check found the complete first step took 10.555 seconds with
the old full-screen OCR preflight. A narrow round-banner hint now avoids that
redundant pass; board() still validates the complete hand, stats, resources and
state. Other phases retain full-screen OCR. The same saved-board dry run then
took 6.596 seconds. No real input was dispatched by those local dry runs.
72 Python tests pass. The PowerShell launcher has an explicit -ReusePairingToken
switch; its syntax parser check passes. Keep the 10-second deadline unchanged.
The running inspect-only server has not yet loaded this latest phase-hint change.

## Resume

1. Observe the user's pairing outcome; do not treat waiting as successful pairing.
2. Keep the game untimed until setup is ready. Confirm full visible canvas at a
   useful resolution and a fresh round-1 Training Bot board.
3. Restart the local server with execution and the same token:
   .\Start-TrainingAgent.ps1 -Execute -ReusePairingToken
   (stop the existing server using the authenticated /shutdown endpoint first).
4. Release/detach ChatGPT browser debugging on the game tab before the extension
   attaches its input debugger. Native screen observations can be used while it
   runs. Never have both browser-debugging clients control the same game tab.
5. Check automatic play and Start only on the fresh Training Bot match. Observe
   actual local receipts and screenshots; stop on any uncertain field or action.
6. Verify the selected card, MIN reset, each increment, one confirmation, and the
   next round's resource receipt. No automatic requeue or Fury is enabled.
7. Stop/restore inspect-only after the bounded test, and report actual outcomes.

Current request remains live calibration, not more offline-only work. If the
user fixes pairing, continue this same test without asking for authorization
again. Browser action policy handoff is the current blocker, not game rules.
