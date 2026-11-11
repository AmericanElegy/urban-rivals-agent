# OCR validation status — 2026-11-11

The latest offline replay checks 375 fields across eleven cases from seven saved
source frames. Results: **370 passed, five unreadable, zero incorrect values**.
This is a local regression set, not an accuracy estimate for unseen matches.

| Field group | Passed | Unreadable | Incorrect |
| --- | ---: | ---: | ---: |
| Screen phase | 11 | 0 | 0 |
| Round, move clock, revealed opponent | 24 | 0 | 0 |
| Life and pillz | 32 | 0 | 0 |
| Names and active-card stats/evolution | 237 | 1 | 0 |
| Played slots and paid pill counts | 66 | 4 | 0 |

The full original extension board passes all 48 fields at native size and at
85%/115% resampling. The native recording round-1 board also passes all 48.
The played-marker classifier separately passes all 64 labeled slot observations.

Remaining unreadable fields:

- Lucien's damage 1 at 85% synthetic resampling of recording round 1.
- Fixit's paid pill count in recording rounds 2 and 3.
- Vermyn Noel's and Barcius's paid pill counts in round 3.

The visible tiny markers in those last four fields are x1: zero paid pillz,
including the free pill in the displayed multiplier. They remain unreadable
because the OCR evidence does not meet the acceptance threshold; the expected
labels do not fill in recognition results. All played-card identities/slots are
recognized, including the dimmed ones. Dimmed stats are not reread or guessed.

Board diagnostics took approximately 9.6–13.4 seconds in this run. This remains
too close to or beyond the bridge's freshness budget for live control. The next
work is narrow digit/font recognition with held-out examples, then profiling and
caching verified static hand data. Unsupported abilities remain another separate
execution blocker. Do not enable automatic play based on this report.

## Reproduce locally

```powershell
.\.venv\Scripts\python.exe -m urban_rivals replay tests/fixtures/ocr_replay.json
```

The command returns exit 1 until every expected field passes. The detailed report
is `local/ocr-replay-report.json`. Media stays local and missing sources fail the
replay. Synthetic resampling does not validate arbitrary responsive layouts.

44 Python tests, six Node extension tests, and a simulator smoke match passed.
No live input was attempted. The running inspect-only bridge was not restarted.
