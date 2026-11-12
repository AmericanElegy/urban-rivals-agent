# Live calibration — 2026-11-11

## Latest live observation

Chrome reconnected as browser 4 (previous browser 3 is unavailable). The existing
signed-in collection tab was navigated through Play to the official WebGL URL.
Menu scroll and Training-card input succeeded without the previous URL guard
failure. In this client, the Training card's yellow Play button launches the
match directly; there is no intervening setup modal. Prepare the bridge before
pressing it on the next run.

The live round-one hand was Fixit, Graff Cr, Joy, Pacarezza versus Gibus,
Viperine, Wilmot, Gregor Ld. Viperine was the revealed lead. All life totals were
15 and pillz totals 12, with 01:42 on the saved capture. No card, pillz or confirm
input was made. Execution remained disabled. The inspect-only bridge was started
with the existing pairing token retained.

Offline diagnostics of a manually cropped fresh browser screenshot passed
147/147 fields at three scales (3.32–4.86 seconds). Manifest:
`tests/fixtures/live_training_ocr.json`. Media/receipts stay ignored in local/.
This validates this board's OCR, not the extension's canvas geometry or automatic
input. The sticky page header partly overlays the top edge: verify complete
canvas visibility through extension geometry before enabling execution.

Unknown-card rejection correctly stops execution on Gibus. The new opponents
need verified exact evolutions and engine coverage for Copy Opp. Ability,
Stop Opp. Bonus, opponent-damage attack scaling, Equalizer damage reduction and
conditional cancellation of power modifiers. Do not simply add catalog entries
before their mechanics are supported and tested.

Pairing was previously resolved by James. An earlier execution attempt ended
when Computer Use could not verify the browser URL, and that execution bridge
was shut down. No automatic live round or full match is confirmed.

## Next bounded test

1. Verify and implement the observed opponent mechanics against official rules.
2. Keep the untimed menu visible until ready; ensure complete canvas visibility.
3. Start the bridge with -Execute -ReusePairingToken only for the bounded test.
4. Use a single input controller: release browser debugging before the extension
   attaches its debugger. Native screen observation may remain available.
5. Verify selected card, MIN, each increment, single confirmation and the next
   round's exact resource receipt. Unknown readings/mechanics must stop.
6. Restore inspect-only after the test. No automatic requeue or own Fury.
