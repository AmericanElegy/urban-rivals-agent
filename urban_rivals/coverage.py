"""Public card-data coverage, distinct from live recognition and validation."""
import json
from collections import Counter, defaultdict
from pathlib import Path
import re


def gap_category(entry):
    """Assign every rejected maximum-level record one primary work category."""
    reason=entry["reason"]
    record=entry["record"]
    text=" ".join(str(record.get(k,"")) for k in ("ability","bonus"))
    folded=text.casefold()
    if reason.startswith("Clock-specific, leader or infiltration"):
        return "special_clans"
    if reason.startswith("Unsupported condition:"):
        return "compound_conditions"
    if re.search(r"\b(poison|toxin|heal|regen|corrosion|combust)\b",folded):
        return "persistent_round_effects"
    if "cancel" in folded and ("pillz" in folded or "life" in folded):
        return "resource_modification_cancellation"
    if "copy" in folded:
        return "remaining_copy_variants"
    if "impose" in folded:
        return "impose_mechanics"
    if re.search(r"\b(cards?|players?|per life|per pillz|pillz lost|life lost)\b",folded):
        return "advanced_scaling_and_team_effects"
    return "ordinary_parser_and_mechanics_tail"


def catalog_coverage():
    data=Path(__file__).parent/"data"
    audit=json.loads((data/"official_catalog_import.json").read_text(encoding="utf-8"))["entries"]
    cards=json.loads((data/"training_cards.json").read_text(encoding="utf-8"))["cards"]
    clans=defaultdict(Counter)
    rejected=[]
    categories=Counter()
    category_examples=defaultdict(list)
    conditions=Counter()
    special_clans=Counter()
    persistent_families=Counter()
    for entry in audit:
        supported=entry["result"] in {"added","existing"}
        card=entry["card"] if supported else entry["record"]
        clans[card["clan"]]["parsed" if supported else "rejected"]+=1
        if not supported:
            category=gap_category(entry)
            categories[category]+=1
            if len(category_examples[category])<8:
                category_examples[category].append({"name":entry["name"],
                    "reason":entry["reason"],"source":entry["source"]})
            if entry["reason"].startswith("Unsupported condition:"):
                conditions[entry["reason"].split(":",1)[1].strip()]+=1
            if category=="special_clans":special_clans[card["clan"]]+=1
            if category=="persistent_round_effects":
                effect_text=" ".join(str(card.get(k,"")) for k in ("ability","bonus")).casefold()
                family=next((name for name in ("poison","toxin","heal","regen","corrosion","combust")
                             if re.search(r"\b"+name+r"\b",effect_text)),"other")
                persistent_families[family.title()]+=1
            rejected.append({"name":entry["name"],"reason":entry["reason"],
                             "category":category,"source":entry["source"]})
    return {
        "source_maximum_level_records":len(audit),
        "parsed_source_records":len(audit)-len(rejected),
        "rejected_source_records":len(rejected),
        "catalog_evolutions":len(cards),
        "catalog_names":len({c["name"].casefold() for c in cards}),
        "clans":{name:dict(counts) for name,counts in sorted(clans.items())},
        "rejection_reasons":dict(Counter(e["reason"] for e in rejected).most_common()),
        "gap_categories":dict(categories.most_common()),
        "gap_category_examples":dict(category_examples),
        "unsupported_conditions":dict(conditions.most_common()),
        "special_clan_gaps":dict(special_clans.most_common()),
        "persistent_effect_gaps":dict(persistent_families.most_common()),
        "rejected_cards":rejected,
        "limits":[
            "Source collection covers maximum-level cards, not every lower evolution.",
            "Parsed effects are not proof of every interacting pair of mechanics.",
            "OCR accuracy and live input validation are separate from catalog coverage.",
            "No completed automatic match has been verified.",
        ],
    }
