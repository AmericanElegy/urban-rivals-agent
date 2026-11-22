# Card reference database — 2026-11-22

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
| Official full evolution tables observed | 2,507 |
| Official level entries observed | 7,930 |
| Preferred level records across current cards | 7,930 |
| Current cards preferring official level tables | 2,507 |
| Current cards retaining wiki candidate tables | 0 |
| Current cards without any evolution-table source | 0 |

Every current official card page now has a validated evolution table. This does
not establish that every historical or removed evolution is represented, nor
does it prove gameplay semantics or format legality.

The official collection validates card identity, ordered levels, power, damage,
ability and bonus text, ability unlock markers, and agreement with the official
maximum-level index. All 2,507 cards and 7,930 rows pass; no required field or
wiki conflict remains unresolved. Five official Day/Night ability pairs and both
GhosTown bonus states are retained as conditional variants. Six damaged accented
names were verified by official card ID and corrected earlier. No mechanics were
enabled as a result of the reference reconciliation.

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

The latter rebuilds `urban_rivals/data/card_reference.json`, writes the checked-in
per-level comparison `urban_rivals/data/reference_reconciliation.json`, and writes
a detailed report to `local/reference-coverage.json`. Rebuilding retains official evolution
observations already in the checked-in snapshot and merges any newer local
observations. An incomplete wiki cache cannot replace the reference snapshot.

## Disagreements and provenance

The source-level comparison covers all 2,507 current cards. Of those, 2,182 have
at least one difference from the retained wiki evidence and 544 have no matching
wiki page. It records 3,777 missing wiki fields, 3,518 differing fields, 1,791
official levels absent from the wiki candidate, and 10 wiki levels absent from
the current official table. Text differences include spelling and punctuation;
they are not all balance changes. Every difference is resolved by preferring the
current official table while retaining the historical wiki evidence and URL.

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
