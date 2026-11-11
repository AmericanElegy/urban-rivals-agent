# OCR validation status — 2026-11-11

The expanded offline replay passes **639/639 fields across seventeen cases** from
seven saved source frames, with zero unreadable or incorrect values. The original
375-check replay also passes completely. This is a local regression set from
one extension capture and one recorded match, not an unseen-match accuracy rate.

| Field group | Passed | Unreadable | Incorrect |
| --- | ---: | ---: | ---: |
| Screen phase | 17 | 0 | 0 |
| Round, move clock, revealed opponent | 42 | 0 | 0 |
| Life and pillz | 56 | 0 | 0 |
| Names and active-card stats/evolution | 394 | 0 | 0 |
| Played slots and paid pill counts | 130 | 0 | 0 |

The five formerly unreadable fields are resolved. Narrow digits use tighter
padding variants with the original confidence/consensus thresholds. Played
counters use a dedicated crop, trimming the touching multiplier-sign fragment
and adding a black border before component filtering. Both diagnostics and the
live reader use the same counter routine; multiplier 1 means zero paid pillz.
Dimmed base stats are retained from a verified initial hand rather than guessed.

Additional checks include 85%/115% resampling of rounds 2 and 3, and 95%/105%
resampling of round 1. These cases were added after the initial digit-padding
experiment and exposed counter-crop failures that were then repaired. They are
regression cases, not a permanently held-out evaluation set. Synthetic resizing
does not prove support for arbitrary responsive layouts or new card fonts.

## Processing time

Board diagnostics took **2.2–5.3 seconds** in the latest expanded replay (first
board 5.26 seconds; subsequent boards approximately 2.2–3.8 seconds), versus the
previous 9.6–13.4 seconds. Profiling found detector inference dominated time:
small text crops were being enlarged to a 736-pixel minimum side. General text
now uses 192 pixels; the clock, revealed title and difficult numeric fallback
retain detailed detection. Detector settings restore even when inference fails.
Unused card artwork no longer incurs played-counter OCR calls.

These are local diagnostic timings, not a live capture/solver/click benchmark.
No first-hand cache was needed for this reduction. Freshness checks and input
safety limits are unchanged. The running inspect-only bridge was not restarted
and has not loaded these on-disk changes.

## Remaining before automatic matches

- Verify and implement unsupported abilities/evolutions; unknown catalog entries
  still block input, including cards in these readable captured hands.
- Validate the full capture, decision, input and round-receipt path in Training
  Bot with a supported hand. No live match is attributed to this program yet.
- Broaden independent source coverage: different hands, fonts, counters, layouts
  and animations. This small recorded set cannot establish general reliability.

## Reproduce locally

```powershell
.\.venv\Scripts\python.exe -m urban_rivals replay tests/fixtures/ocr_replay.json
```

The command now returns exit 0 on the local source set. Detailed output is
`local/ocr-replay-report.json`. Media remains ignored and local; missing sources
fail the replay. No API, paid call, new pairing or new match was required.

48 Python tests, six Node extension tests and a simulator smoke match pass.
