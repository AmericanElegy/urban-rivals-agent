# Urban Rivals mechanics: what the engine knows

Source of truth for each rule is listed. "Official" = https://www.urban-rivals.com/game/rules/.
"Card text" = the official per-card ability descriptions stored in `data/card_reference.json`
(collected from urban-rivals.com character pages).
Coverage: **2,483 of 2,507** official max-level cards parse fully (99%, was 68.6%).
Cards that don't parse still play, but their unparsed text is treated as blank.

## Core fight (modeled)

| Rule | How it works | Source |
|---|---|---|
| Attack | Power × (paid Pillz + 1 free). Attack modifiers apply after Pillz, so they don't scale. | Official |
| Winner / Damage | Higher Attack wins and deals its Damage to the opponent's Life. | Official |
| Ties | Fewer stars wins; same stars, the card played first wins. | Wikipedia (Urban Rivals article) |
| Fury | 3 Pillz for +2 Damage; Cancel Opp. Damage doesn't remove it. | Official |
| Bonus | Active when 2+ cards of the clan are in your hand (played cards still count). | Official |
| Match end | KO, or more Life after round 4. | Official |

## Conditions (modeled)

| Condition | Active when | Source |
|---|---|---|
| Courage / Reprisal | Card played first / second this round | Official |
| Confidence / Revenge | You won / lost the previous round (never round 1) | Official |
| Symmetry / Asymmetry | Opposing card is / isn't in front of yours | Official |
| Day / Night | Game clock (read from screen) | Official |
| Unison / Disunion | All / not all your cards share the clan | Repo (prior work) |
| Bet > N / Bet < N | Pillz on the card (with the free pill) above / below N | Repo (prior work) |
| Defeat / Victory Or Defeat | Card lost / either result (Life & Pillz effects only) | Official |
| **Killshot** | Won with at least 2× the opposing Attack | Official |
| **Perfect** | Won with exactly the Pillz needed (one fewer would have lost; 0 paid counts) | James (player) |
| **Stop:** | Only when an opposing Stop Opp. Ability hits this card | Official |

## Modifiers and scaling (modeled)

Power / Damage / Attack / Life / Pillz ± with Min / Max; Growth, Degrowth, Support, Brawl,
Equalizer, Per Opp. Power/Damage, Per Life/Pillz Left, Life/Pillz Per Damage (Official).

## Interactions (modeled)

| Mechanic | Behaviour | Source |
|---|---|---|
| Stop Opp. Ability / Bonus | Removes the opposing ability / bonus | Official |
| Protection | Shields a stat (or Ability/Bonus) from reducers and Stops; weaker than Cancel | Official |
| Cancel Opp. Power/Damage/Attack Modif. | Removes that type of opposing modifier | Official |
| **Cancel Opp. Life / Pillz Modif.** | Removes opposing Life/Pillz modifiers; pauses their Poison/Heal/Toxin/Regen (Life) or Consume/Dope (Pillz) for that round only | Official |
| Copy | Takes the opposing starting Power/Damage, or its Ability/Bonus | Official |
| Exchange | Swaps starting values; beats Copy of the same type | Official |
| **Impose** | Forces your starting Power/Damage onto the opposing card | Official |
| Tune Out | Fight decided on Pillz instead of Attack | Repo (prior work) |
| Recover X Pillz Out Of Y | Defeat: get back a fraction of Pillz played (rounded down, min 1) | Official |
| **Backlash** | Your own player pays the Life/Pillz/Poison cost when the card wins | Official + wiki |

## Effects that last across rounds (modeled)

| Effect | Ticks | Bound | Source |
|---|---|---|---|
| Poison | End of each round **after** the one it was won in | Opponent Life ≥ Min | Official |
| Heal (Care) | Same timing, on you | Your Life ≤ Max | Official |
| Toxin / Regen | Also at the end of the round played | Min / Max | Official |
| Consume / Dope | Pillz versions of Toxin / Regen | Min / Max | Official |
| Corrosion | A Poison worth X × the round it was played; win or lose | Min | Card text |
| Mindwipe | Toxin-style: opponent loses X Life **and** Pillz each round | Min | Card text |
| Combust | Poison-style: opponent loses X Life and Pillz from the next round | Min | Card text |
| Repair | Regen-style: you gain X Life and Pillz | Max | Card text |
| Slots | Poison/Toxin/Corrosion share one slot, Heal/Regen another; the newer replaces the older "as soon as the latter takes effect" | | Card text |

## More card-text mechanics (modeled)

| Mechanic | Behaviour | Source |
|---|---|---|
| After [clans] | Active if your previous-round card was one of those clans (an Oculus never counts) | Card text (clans from each card's description) |
| Versus [clans] | Active if the opponent's hand holds one of those clans | Official + card text |
| Chained conditions | e.g. "Day: Courage: Attack +20" — all must hold | Card text |
| Reanimate | On defeat, +X Life and you can't be KO'd by that damage | Card text |
| KO is final | Other Life gains don't bring a KO'd player back | Card text (Limitless/Reanimate wording) |
| Corrupt | Win or lose, your own Life −X (Min) | Card text |
| Xantiax / "Players" | Both players are affected | Card text |
| "Cards" | Both fighting cards are affected | Card text |
| Per Life/Pillz Lost | Scales with Life/Pillz lost since the match started (12/12) | Card text |
| Per Opp. Damage (Life) | Life gain × opposing Damage | Card text |
| Team | Every card in your deck gets the ability | Card text |
| Cancel Leader | Leader abilities off with more than one Leader in the deck | Card text |
| Infiltrated (Oculus) | Takes the only other clan, or the sole card's clan with two others; none with three or 2+ Oculus | Official + card text |
| Conditional Copy | e.g. "Reprisal: Copy Opp. Bonus" checks its condition first | Card text |
| Perfection / Sinister Symmetry / Fatal Killshot | Win the match by KO on Perfect / Symmetry / Killshot win | Card text |
| Tie-break | Wins equal attacks (cancelled if both have it) | Card text |
| Bypass / Remove Ability Conditions | Deck-wide passives | Card text |
| Counter-attack | Play order; read from the screen, nothing to model | Card text |

## Modeled, but an assumption is unverified

- **Growth: Poison/Heal** — multiplied by the round it was won in, not re-multiplied each tick.
- **Fury vs. damage reducers** — "-X Opp. Damage" also reduces Fury's +2.
- **Order of end-of-round effects** — damage, Life/Pillz effects, lingering ticks, then new effects.
- **Mindwipe/Combust/Repair slots** — treated as their Life and Pillz parts (Toxin+Consume, Poison+rot, Regen+Dope).
- **Tie-break at match end** — only round ties are modeled; a tied final Life still counts as a tie.
- **Starting Life/Pillz** for "Lost" scaling — assumed 12/12.

## Not modeled yet (treated as blank text) — 24 cards

| Gap | Cards | Why |
|---|---|---|
| Copy in rare forms | ~6 | Conditions after the fight / recursive copies |
| After/Versus whose description doesn't list clans | 8 | Clan list missing from the stored description |
| Per-damage gains on defeat | 3 | Wording unclear |
| Rebirth, Overdose, Limitless, Hazard, Illusion, Beyond | 6 | Randomness, hidden cards, or a 5th round |
| +1 Pillz Per Round / −1 Opp. Pillz Per Round | 2 | Start-of-round passives |

Run `python -m urban_rivals coverage` for current counts.
