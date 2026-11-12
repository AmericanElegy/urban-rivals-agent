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

## Fresh Training hand follow-up

Checked the official rules again on 2026-11-11:
https://www.urban-rivals.com/game/rules/
The Cancel, Stop Ability/Bonus, Per Opp. Power/Damage, Exchange and Equalizer
sections support these new simulator additions:

- Stop Opp. Bonus removes bonus effects while retaining surviving abilities.
  An ability-sourced Stop Bonus disabled by Stop Ability does not remove a bonus.
  Cross-source Stop Ability/Bonus cycles remain rejected pending precedence evidence.
- Cancel Opp. Power/Damage Modif removes the opposing card's modifiers of that
  stat from both ability and bonus, including reducers aimed back at the user.
  Cancel also prevents the matching Exchange; damage cancellation retains Fury.
- Positive Attack Per Opp. Power/Damage scales from the opponent's printed base
  stat, before modifiers. Equalizer already existed; its damage-reduction path
  now has an explicit regression case based on the observed Wilmot text.

Twelve new tests cover these mechanics and rejection boundaries. All 87 Python
tests pass; the four recorded boards still reconcile three completed rounds.
These additions have unit evidence, not new live resource-receipt evidence.

The general official Copy section describes copying bonus/power/damage but does
not document Copy Opp. Ability or its resolution with Stop, conditional abilities
and Exchange. Copy Opp. Ability remains rejected. The new live hand's cards have
not been added to the executable catalog, avoiding omitted or guessed effects.
Next: obtain the official character/bonus description for those exact evolutions
and verify ability-copy precedence before enabling that hand.

## Ability-copy implementation and full battle-log consistency

The official Gibus page supplies the missing bonus definition:
https://www.urban-rivals.com/game/characters/?id_perso=2261
Copy Ability replaces its own effect with the original opposing ability;
Leader/Genesis abilities are excluded. Replacement preserves its source, so a
bonus copy remains bonus-sourced. Copied conditions and multipliers use the
copier's initiative, history, clan and opposing stats. Recursive/conditional
copy remains rejected, as do unverified cross-source stop cycles.

Exact observed evolutions were checked against the signed-in official collection
and character evolution rows:
- Gibus (2261): Oblivion, 6/4/3, +3 Attack Per Opp. Damage.
- Viperine (2508): Oblivion, 9/3/3, Unison Stop Bonus.
- Wilmot (2250): Oblivion, 7/6/5, Equalizer damage reduction minimum 1.
- Gregor Ld (2028): Paradox, 9/5/5, Asymmetry Cancel Opp. Power Modif.
  The generic sheet displayed a lower-evolution Protection ability; the
  maximum-evolution row, collection row and actual board agree on Cancel.
- Mercury Cr (1227): Pussycats, 8/4/4, +2 Pillz.
- Veronica (745): Pussycats, 7/5/4, -2 Opp. Pillz minimum 1 on victory.
- Eris (575): Sakrohm, 7/7/5, Courage +2 Life.
- Sol Hona (724): Sakrohm, 6/8/5, -2 Opp. Power minimum 6.
Card URLs use https://www.urban-rivals.com/game/characters/?id_perso=ID.
Printed clan bonuses are preserved, even on singleton Gregor (inactive there).

The completed Oblivion match's reverse-order battle log was transcribed with
account identifiers omitted. Chronological receipts: Joy vs Viperine,
Fixit vs Gregor, Pacarezza vs Gibus, Graff vs Wilmot. Life progression:
15/15 -> 15/9 -> 10/9 -> 10/3 -> 10/2. Log bids include the free pill.
Enumerating affordable Fury flags produces seven consistent complete histories.
Our third-round Fury is required; opposing Fury choices and final reserves are
not uniquely observable. verify-log retains all candidates, avoiding invented
opposing expenditures. This corroborates copied Stop Ability and the conditional
Exchange/Fury path, but is not an automatic-bot match or proof of every mechanic.

## Printed damage copy, attack cancellation and catalog expansion (2026-11-12)

Official Kreenk Ld page (id_perso=809) defines Damage Copy using printed opposing
damage, excluding ability, bonus and Fury. Official Yang Luhan (2459) defines
Attack Cancel as disabling opposing attack increases/reductions while preserving
attack gained through pillz. Both are implemented and interaction-tested with
Stop Ability, damage cancellation, Exchange precedence and own Fury.

Chlora (697), Dixie (1467), Jenny (336), Lord Oon Ld (1751), Kati (349), Yoshito
(2240) were checked at their exact observed/max levels. Lord Oon is Dominion;
his Growth bonus was inactive as a singleton in the observed Fang Pi hand.

Rendered official clan pages expose maximum-level facts. All 36 lists were
expanded with Display all; each list's visible count was checked against its
heading. The source corpus totals 2,507 cards. Conservative import rejects
unsupported text and special-rule clans; no modifiers are dropped to load a
card. The catalog now has 1,358 exact evolutions / 1,355 distinct names. Existing
seed evolutions take precedence for named replay fixtures; live recognition uses
observed stats/stars, retaining the chosen evolution through the match.
Official source links and all rejection reasons are recorded in
urban_rivals/data/official_catalog_import.json. This is broader mechanic parsing
and source coverage, not proof of live correctness for every new interaction.
