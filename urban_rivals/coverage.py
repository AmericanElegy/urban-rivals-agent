"""Public card-data coverage, distinct from live recognition and validation."""
import json
from collections import Counter, defaultdict
from pathlib import Path


def catalog_coverage():
    data=Path(__file__).parent/"data"
    audit=json.loads((data/"official_catalog_import.json").read_text(encoding="utf-8"))["entries"]
    cards=json.loads((data/"training_cards.json").read_text(encoding="utf-8"))["cards"]
    clans=defaultdict(Counter)
    rejected=[]
    for entry in audit:
        supported=entry["result"] in {"added","existing"}
        card=entry["card"] if supported else entry["record"]
        clans[card["clan"]]["parsed" if supported else "rejected"]+=1
        if not supported:
            rejected.append({"name":entry["name"],"reason":entry["reason"],"source":entry["source"]})
    return {
        "source_maximum_level_records":len(audit),
        "parsed_source_records":len(audit)-len(rejected),
        "rejected_source_records":len(rejected),
        "catalog_evolutions":len(cards),
        "catalog_names":len({c["name"].casefold() for c in cards}),
        "clans":{name:dict(counts) for name,counts in sorted(clans.items())},
        "rejection_reasons":dict(Counter(e["reason"] for e in rejected).most_common()),
        "rejected_cards":rejected,
        "limits":[
            "Source collection covers maximum-level cards, not every lower evolution.",
            "Parsed effects are not proof of every interacting pair of mechanics.",
            "OCR accuracy and live input validation are separate from catalog coverage.",
            "No completed automatic match has been verified.",
        ],
    }
