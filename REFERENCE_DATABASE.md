# Card reference database — 2026-11-12

The reference stores facts even when the gameplay engine cannot simulate them.
It does not change the live execution catalog or authorize unknown mechanics.

## Current coverage

| Source or result | Count |
| --- | ---: |
| Official maximum-level cards | 2,507 |
| Wiki public pages acquired through the API | 4,025 |
| Wiki card records parsed | 2,005 |
| Wiki level entries retained | 6,279 |
| Wiki cards matched to current official names | 1,964 |
| Official full evolution tables observed | 711 |
| Official level entries observed | 2,313 |
| Preferred level records across current cards | 7,927 |
| Current cards preferring official level tables | 711 |
| Current cards retaining wiki candidate tables | 1,796 |
| Current cards without any evolution-table source | 0 |

These counts do not establish that every historical or currently legal evolution
is present or current. Wiki-only lower levels remain candidates. A card can have
matching maximum-level stats and outdated lower-level stats or abilities.

The official targeted collection covered missing wiki cards, malformed levels,
maximum-stat differences, ambiguous ability unlocks and known lower-level
disagreements. Six damaged accented names were verified by official card ID and
corrected in the source audit and gameplay catalog. No mechanics were enabled
as a result of those corrections.

## Lookup and refresh

Run from this checkout using its installed Python environment:

```powershell
.venv\Scripts\python.exe -m urban_rivals reference "Fixit"
.venv\Scripts\python.exe -m urban_rivals coverage
```

`reference` returns official maximum-level facts, preferred level records,
source tables and wiki disagreements. An official observed table takes priority
over wiki candidates. It preserves each level's ability text and unlock marker.
Unknown wiki ability unlocks stay unknown; they are not invented from max-level
text. `coverage` continues to report the separate gameplay-parser coverage.

The public wiki collector resumes from cached batches and uses no credentials:

```powershell
.venv\Scripts\python.exe -m urban_rivals.wiki_reference
.venv\Scripts\python.exe -m urban_rivals.reference_database
```

The latter rebuilds `urban_rivals/data/card_reference.json` and writes a detailed
report to `local/reference-coverage.json`. Rebuilding retains official evolution
observations already in the checked-in snapshot and merges any newer local
observations. An incomplete wiki cache cannot replace the reference snapshot.

## Disagreements and provenance

The wiki/official comparison records 88 differing maximum-stat records, 13
missing wiki maximum levels, and 523 ability-text differences requiring review.
Text differences include spelling and punctuation; they are not all balance
changes. They are retained rather than silently overwritten. Official targeted
tables resolve acquisition gaps, while the historical wiki evidence remains.

For example, the wiki's four-star Fixit is 7/5 with a general Protection entry.
The current official table shows 7/6 with Reprisal Protection. The lookup prefers
the official row, and a regression test checks that choice.

Wiki records include page URLs, revision IDs, revision timestamps and attribution
to the Urban Rivals Wiki, whose content is offered under CC-BY-SA unless otherwise
noted: https://www.fandom.com/licensing. Only structured card facts are included
in the checked-in reference; strategy prose and artwork are not copied.

Sources evaluated:

- https://urban-rivals.fandom.com/wiki/Dr_Saw — level table matches the official sample.
- https://urban-rivals.fandom.com/api.php — public batch acquisition, 81 cached batches.
- https://www.urban-rivals.com/game/characters/?id_perso=884 — current Fixit levels.
- https://github.com/pakoito/CardsFromUrbanRivals — evaluated but not imported:
  2,272 cards, one level per card; it does not fill the evolution gap.

The reference has no account identifiers, holdings, prices, cookies or credentials.
Raw wiki responses and research downloads stay ignored under `local/`.
