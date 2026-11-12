# OCR validation status — 2026-11-11

The expanded offline replay passes **764/764 fields across twenty cases** from
eight saved source frames, with zero unreadable or incorrect values. The original
375-check replay also passes completely. This is a local regression set from
one extension capture and one recorded match, not an unseen-match accuracy rate.

| Field group | Passed | Unreadable | Incorrect |
| --- | ---: | ---: | ---: |
| Screen phase | 20 | 0 | 0 |
| Round, move clock, revealed opponent | 51 | 0 | 0 |
| Catalog/recognition readiness | 17 | 0 | 0 |
| Life and pillz | 68 | 0 | 0 |
| Names and active-card stats/evolution | 436 | 0 | 0 |
| Played slots and paid pill counts | 172 | 0 | 0 |

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

A newly extracted stable round-4 board at 57 seconds adds six played counters,
including Buford's x4. The corpus now also checks recognition/catalog readiness:
recording hands pass; the Montana capture remains blocked on unknown cards.
Narrow counter failures can use two agreeing shifted crops, with the same
numeric confidence rules.

## Processing time

Board diagnostics took **3.0–7.1 seconds** in the latest 20-case replay (first
board 6.79 seconds). The earlier 17-case run measured 2.2–5.3 seconds. The new
resampled round-4 counters require extra fallback reads. The older implementation
measured 9.6–13.4 seconds on its original source set. These runs are local timings,
not a controlled speed benchmark. Profiling found detector inference dominated time:
small text crops were being enlarged to a 736-pixel minimum side. General text
now uses 192 pixels; the clock, revealed title and difficult numeric fallback
retain detailed detection. Detector settings restore even when inference fails.
Unused card artwork no longer incurs played-counter OCR calls.

These are local diagnostic timings, not a live capture/solver/click benchmark.
No first-hand cache was needed for this reduction. Freshness checks and input
safety limits are unchanged. The local bridge has now been refreshed in inspect-only mode with the existing
pairing token retained; authenticated readiness passed.

## Remaining before automatic matches

- Broaden supported abilities/evolutions beyond the eighteen-entry catalog. The
  recorded Bangers/Cosmohnuts hand is now fully covered; Montana is still blocked.
  See [MECHANICS_STATUS.md](MECHANICS_STATUS.md) for exact mechanic scope.
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

71 Python tests, six Node extension tests, a simulator smoke match and offline
verification of four sequential native boards pass. No live inputs were issued.

## Additional panel and fresh-board calibration

The fresh Oblivion board passes 147/147 fields at three scales, now including
engine readiness. tests/fixtures/live_training_ocr.json references local media.
Four recorded stake panels (Fixit, Vermyn Noel, Bennie, Pacarezza) pass 48/48
checks at three scales via tests/fixtures/stake_panels.json. Dedicated purple
Attack and pink Damage masks retain the two-read confidence requirement.
The old title crop returned B FIXIT, B BENNIE, etc. Tightening it to the title
band excludes the clan logo and reads all four exact names.

Execution waits for two consecutive matching panel readings before MIN, each
increment and confirmation. Stale attack after increment stops instead of
repeating the click. These are replay/controller checks; live panel input and
an automatic completed match remain pending. Do not run multiple OCR replays
alongside live execution: CPU contention can exceed the 10-second frame limit.
