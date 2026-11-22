# Mechanics gap inventory — 2026-11-22

This report measures the executable maximum-level catalog after the reconciled
official facts were reprocessed with `python -m urban_rivals.catalog_import`.
The refresh added zero records and produced byte-identical catalog and audit
files, confirming that the current import is deterministic.

## Coverage

| Measure | Count |
| --- | ---: |
| Official maximum-level records | 2,507 |
| Parsed maximum-level records | 1,719 |
| Rejected maximum-level records | 788 |
| Executable catalog evolutions | 1,726 |
| Executable catalog names | 1,723 |

Maximum-level parser coverage is 68.6%. These numbers do not measure historical
or lower-level evolutions, live OCR accuracy, interaction completeness, format
legality, or successful automatic play.

## Exhaustive primary categories

Every rejected record is assigned exactly one primary category. The counts sum
to all 788 rejections.

| Category | Records | Share of rejections |
| --- | ---: | ---: |
| Persistent round effects | 200 | 25.4% |
| Compound conditions | 175 | 22.2% |
| Special clans | 155 | 19.7% |
| Ordinary parser/mechanics tail | 141 | 17.9% |
| Advanced scaling and team effects | 60 | 7.6% |
| Resource-modification cancellation | 27 | 3.4% |
| Remaining Copy variants | 22 | 2.8% |
| Impose mechanics | 8 | 1.0% |

The ordinary tail includes isolated punctuation aliases and mechanics such as
Dope, Consume, combined stat spellings, simple opponent-resource modifiers and
other low-frequency forms. It must be split and verified before implementation;
the category is not permission to parse them heuristically.

## Persistent effects

| Family | Rejected records |
| --- | ---: |
| Poison | 139 |
| Heal | 29 |
| Toxin | 14 |
| Regen | 11 |
| Combust | 5 |
| Corrosion | 2 |

These 200 records are the largest ordinary mechanics block. They require match
state that survives round resolution, explicit activation/replacement timing,
minimum/maximum bounds, and receipt reconciliation.

## Compound conditions

| Condition | Rejected records |
| --- | ---: |
| Stop | 70 |
| Killshot | 32 |
| After | 21 |
| Versus | 18 |
| Backlash | 14 |
| Perfect | 7 |
| Reanimate | 6 |
| Xantiax | 3 |
| Vict. Or Def. alias | 3 |
| Conf. alias | 1 |

These counts measure the primary parser failure. A card can still contain
another mechanic that will remain unsupported after its condition is added.

## Special clans kept separate

| Clan | Rejected records |
| --- | ---: |
| Oculus | 75 |
| GhosTown | 59 |
| Leader | 21 |

These 155 records remain outside ordinary bulk import. Oculus infiltration,
GhosTown clock variants and Leader team rules need dedicated state and validation.

## Recommended continuation

1. Persistent Poison/Toxin/Heal/Regen state, with Combust and Corrosion kept
   gated until their distinct timing is verified.
2. Compound Stop, Killshot, After, Versus and Backlash conditions.
3. Opposing Pillz/Life modification cancellation (27 records).
4. Re-run this inventory and split the 141-record ordinary tail by verified rule.
5. Keep special-clan work separate, then return to controlled Training Bot
   validation only after offline receipts remain stable.

The detailed local report at `local/catalog-coverage.json` retains every rejected
card, official source URL, exact reason, category and representative examples.
It contains no credentials or account data and remains ignored as runtime output.
