# Mechanics and recorded-match validation — 2026-11-11

The simulator now supports Power/Damage Protection, conditional Power/Damage
Exchange, Tune Out, and strict Bet comparisons. The catalog contains eighteen
specific evolutions, including the complete Bangers/Cosmohnuts hand in James's
recording. This remains a supported subset, not a general card database.

## Sources checked

- [Official game rules](https://www.urban-rivals.com/game/rules/): Protection,
  Exchange, Stop Ability, Reprisal, Fury, and post-round resource modifications.
- [Austin](https://www.urban-rivals.com/game/characters/?id_perso=2599): 7/8 at
  five stars, Bet > 5 Pillz damage reduction, and the Tune Out definition.
- [Barcius](https://www.urban-rivals.com/game/characters/?id_perso=2386): 8/4 at
  three stars and Confidence: +3 Life.
- [Buford](https://www.urban-rivals.com/game/characters/?id_perso=2638): 7/3 at
  three stars and Bet > 3 Pillz: -4 Opp. Life, Min 3.
- [Lucien](https://www.urban-rivals.com/game/characters/?id_perso=2377): 8/1 at
  four stars and -6 Opp. Life, Min 0.

The official card pages were read in the existing signed-in Chrome session.
Only public card information was retained. Temporary research tabs were closed;
no deck, collection, market, match or account change was made.

## Implemented behavior

Protection suppresses negative modifiers of the protected stat, while preserving
positive modifiers. Stop Ability removes ability-sourced Protection. Exchange
swaps starting stats before modifiers and Fury, bypassing Protection. Two active
same-stat Exchanges are rejected because that interaction remains unverified.

Tune Out substitutes attack-pill allocation for Attack in the round comparison;
stars and initiative still break ties. Its clan bonus requires two original-hand
clan members, including used cards. Bet includes the free pill, excludes Fury's
separate cost, and uses a strict comparison. Resource changes still require the
appropriate round outcome. Fury-related Tune Out behavior has unit coverage but
has not been reconciled against a recorded Fury round.

Stop Ability now strips effects by their recorded ability/bonus source, avoiding
a same-stat/same-condition collision when Bet thresholds differ.

## Evidence

The engine reproduces three completed rounds from the supplied recording:

| Completed round | Our move | Opponent move | Next life (us/them) | Next pillz (us/them) |
| --- | --- | --- | --- | --- |
| 1 | Fixit, 0 paid | Austin, 5 paid | 7 / 15 | 12 / 7 |
| 2 | Vermyn Noel, 0 paid | Barcius, 0 paid | 7 / 11 | 12 / 7 |
| 3 | Bennie, 0 paid | Buford, 3 paid | 3 / 11 | 12 / 4 |

Round 2 exercises Tune Out: lower-Power Vermyn wins the equal-Pillz contest by
stars. Round 3 exercises Bet's free-pill boundary and delayed life adjustment.
The 55-second animation temporarily shows life 4; the stable 57-second ROUND 4
board shows life 3. Treat the animation as an intermediate state.

`verify-match` runs the real board reader and receipt reconciliation on four
native board images. It verifies names, initiative, revealed opponent, life,
pillz, used cards and previous-round winners through the start of round 4.
It does not bypass the live reader with hand-entered states. The separate unit
receipt test also runs without OCR or private source media.

```powershell
.\.venv\Scripts\python.exe -m urban_rivals verify-match tests/fixtures/recorded_match.json
.\.venv\Scripts\python.exe -m urban_rivals advise examples/recorded_training.json --observed-card 0 --iterations 100
```

Detailed match output stays in ignored `local/match-verification.json`. The
advice command is an offline what-if; its sample is not a played move or a match
win-rate estimate. The original two older round receipts also remain passing.

## Remaining scope

No automatic live match or click is attributed to the program. The fourth
recorded round's final submission is not inferred from an incomplete animation.
Protection/Exchange have targeted rule-based interaction tests, but no supplied
receipt isolates their active effects. They remain pending live validation.

Copy, ongoing poison/toxin effects, Stop Bonus, Protection Ability/Bonus and many
other mechanics remain rejected. Dr Elisa, Mendossa and Caballine stay outside
the catalog. The Montana capture therefore remains blocked. The recording hand
can now be fully recognized; that readiness flag does not enable execution.
The local bridge was refreshed in inspect-only mode with the existing pairing
token retained, and authenticated readiness succeeded. No extension reload or
new pairing is needed. Live action-panel/round-end validation is still required.
