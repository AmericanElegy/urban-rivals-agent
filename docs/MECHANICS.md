# Urban Rivals mechanics: what the engine knows

Source of truth for each rule is listed. "Official" = https://www.urban-rivals.com/game/rules/.
Coverage after this audit: **2,158 of 2,507** official max-level cards parse fully (86%, was 68.6%).
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
| Replacement | A second effect of the same kind replaces the first | | Official |

## Modeled, but an assumption is unverified

- **Growth: Poison/Heal** — multiplied by the round it was won in, not re-multiplied each tick.
- **Fury vs. damage reducers** — "-X Opp. Damage" also reduces Fury's +2.
- **Per Pillz Left** — counts Pillz before this round's bet.
- **Order of end-of-round Life effects** — damage, then Life/Pillz effects, then lingering ticks, then new effects.

## Not modeled yet (treated as blank text)

| Gap | Cards | What's needed |
|---|---|---|
| Oculus "Infiltrated" | 75 | Clan-switching rule; the official two-clan wording is inconsistent |
| GhosTown combos (e.g. "Day: Courage: …") | 59 | Two conditions on one effect |
| After | 26 | Definition (not on the rules page) |
| Cancel Leader / Leader cards | 21 | Leader rules |
| Versus | 18 | Card data omits *which* clan is named |
| Players / Cards (affect both sides) | ~15 | Straightforward; next batch |
| Per Life Lost / Per Pillz Lost | ~15 | Starting Life per mode |
| Reanimate, Mindwipe, Combust, Corrosion, Repair, Rebirth, Xantiax | ~20 | Definitions (not on the rules page) |
| One-off specials (Overdose, Limitless, Hazard, Illusion, Bypass, Counter-attack, Beyond, …) | ~10 | Individual definitions |

Run `python -m urban_rivals coverage` for current counts.
