"""Source-preserving card reference, independent of the effect parser."""
import html
import json
from pathlib import Path
import re
from urllib.parse import quote
from collections import Counter
from .vision import normalize


def plain(value):
    value=re.sub(r"<!--.*?-->","",value,flags=re.S)
    value=re.sub(r"\[\[([^\[\]]+)\]\]",lambda m:m[1].split("|")[-1],value)
    value=re.sub(r"<[^>]+>","",value)
    return " ".join(html.unescape(value).replace("'''","").replace("''","").split())


def wiki_card(page):
    revision=page.get("revisions",[{}])[0]
    text=revision.get("slots",{}).get("main",{}).get("*","")
    start=re.search(r"\{\{[ \t]*Infobox[ _]character\b",text,re.I)
    fields={}
    if start:
        # Only this infobox: prose, strategy and unrelated tables are excluded.
        depth=1
        cursor=start.end()
        end=cursor
        while depth and end<len(text)-1:
            if text[end:end+2]=="{{":depth+=1;end+=2
            elif text[end:end+2]=="}}":depth-=1;end+=2
            else:end+=1
        box=text[cursor:end-2]
        fields={m[1].strip().lower():plain(m[2]) for m in re.finditer(
            r"^\|[ \t]*([\w]+)[ \t]*=[ \t]*(.*?)(?=^\||\Z)",box,re.M|re.S)}
    def table_field(name):
        match=re.search(r"^\|[ \t]*"+name+r"[ \t]*\r?\n\|([^\n]+)",text,re.M|re.I)
        return plain(match[1]) if match else ""
    clan=fields.get("clan") or table_field("Clan")
    ability=fields.get("ability") or table_field("Ability")
    bonus=fields.get("bonus") or table_field("Bonus")
    levels=[]
    for level in range(1,6):
        value=fields.get(f"level{level}","")
        if not value:
            match=re.search(r"^\|[ \t]*Stats[ \t]+lv[l]?[ .]*"+str(level)+r"[ \t]*\r?\n\|([^\n]+)",text,re.M|re.I)
            value=plain(match[1]) if match else ""
        if not value:continue
        match=re.fullmatch(r"(\d+)\s*/\s*(\d+)(?:\s*\(([^)]*)\))?",value)
        if not match:
            levels.append({"level":level,"raw":value,"error":"Unparsed level statistics"})
        else:
            levels.append({"level":level,"power":int(match[1]),"damage":int(match[2]),
                           "note":match[3] or ""})
    if not clan or not levels:return None
    unlock=fields.get("abilitylevel","")
    unlock=int(unlock) if re.fullmatch("[1-5]",unlock) else None
    note_levels=[e["level"] for e in levels if re.search(r"(?:gains ability|ability (?:activated|unlocked))",e.get("note",""),re.I)]
    if unlock is None and len(note_levels)==1:unlock=note_levels[0]
    return {"name":page["title"],"clan":clan,"ability":ability,"bonus":bonus,
            "ability_unlock_level":unlock,"levels":levels,
            "source":{"kind":"wiki","url":"https://urban-rivals.fandom.com/wiki/"+quote(page["title"].replace(" ","_")),
                      "revision":revision.get("revid"),"timestamp":revision.get("timestamp"),
                      "license":"CC-BY-SA; see https://www.fandom.com/licensing"}}


def build_reference(cache="local/wiki-reference-cache",official_evolutions="local/official-evolutions.jsonl"):
    root=Path(__file__).parent/"data"
    audit=json.loads((root/"official_catalog_import.json").read_text(encoding="utf-8"))["entries"]
    official=[]
    for entry in audit:
        c=dict(entry.get("card",entry.get("record")))
        c.pop("url",None)
        level=c.pop("stars")
        official.append({**c,"level":level,"source":{"kind":"official","url":entry["source"]}})
    by_name={normalize(c["name"]):c for c in official}
    wiki=[]
    cache_paths=sorted(Path(cache).glob("batch-*.json"))
    pages_seen=0
    last_batch={}
    for path in cache_paths:
        data=json.loads(path.read_text(encoding="utf-8"))
        last_batch=data
        pages_seen+=len(data.get("query",{}).get("pages",{}))
        for page in data.get("query",{}).get("pages",{}).values():
            card=wiki_card(page)
            if card:wiki.append(card)
    conflicts=[]
    for card in wiki:
        current=by_name.get(normalize(card["name"]))
        card["official_name_match"]=current is not None
        card["official_maximum_stats_match"]=False
        if current:
            level=next((e for e in card["levels"] if e["level"]==current["level"]),{})
            same=all(level.get(k)==current[k] for k in ("power","damage"))
            card["official_maximum_stats_match"]=same
            if not same:conflicts.append({"name":card["name"],"kind":"maximum_stats" if level else "maximum_level_missing","official":{k:current[k] for k in ("level","power","damage")},"wiki":level})
            if normalize(card["ability"])!=normalize(current["ability"]):
                conflicts.append({"name":card["name"],"kind":"ability_text_requires_review",
                                  "official":current["ability"],"wiki":card["ability"]})
    # A checkout already contains public official observations. Preserve those
    # when a new machine has only the checked-in snapshot and a fresh wiki cache.
    snapshot=root/"card_reference.json"
    verified=(json.loads(snapshot.read_text(encoding="utf-8")).get("official_evolution_pages",[])
              if snapshot.exists() else [])
    verified_by_url={p["url"]:p for p in verified}
    path=Path(official_evolutions)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line:
                observation=json.loads(line)
                verified_by_url[observation["url"]]=observation
    verified=list(verified_by_url.values())
    cache_complete=bool(cache_paths) and "continue" not in last_batch and all(
        path.name==f"batch-{i:04d}.json" for i,path in enumerate(cache_paths))
    if not cache_complete:
        raise ValueError("Wiki cache is incomplete; finish collection before replacing the reference snapshot")
    return {"schema":"urban-rivals/reference/v1",
            "wiki_acquisition":{"public_pages":pages_seen,"batches":len(cache_paths),"complete":cache_complete},
            "official_maximum_levels":official,
            "wiki_candidates":wiki,"official_evolution_pages":verified,
            "conflicts":conflicts,
            "limits":["Wiki candidates never enable live actions automatically.",
                      "Matching maximum stats does not verify lower levels or ability text.",
                      "Official evolution pages take precedence over wiki candidates.",
                      "Missing or ambiguous ability unlock levels remain unknown."]}


def reference_report(data):
    wiki={normalize(c["name"]):c for c in data["wiki_candidates"]}
    verified_urls={p["url"] for p in data["official_evolution_pages"]}
    gaps=[]
    for card in data["official_maximum_levels"]:
        candidate=wiki.get(normalize(card["name"]))
        if candidate is None:
            gaps.append({"name":card["name"],"reason":"No wiki evolution record","url":card["source"]["url"]})
        elif any("error" in e for e in candidate["levels"]):
            gaps.append({"name":card["name"],"reason":"Unparsed wiki level statistics","url":card["source"]["url"]})
    return {"wiki_acquisition":data.get("wiki_acquisition"),
            "official_maximum_level_cards":len(data["official_maximum_levels"]),
            "wiki_cards":len(data["wiki_candidates"]),
            "wiki_level_entries":sum(len(c["levels"]) for c in data["wiki_candidates"]),
            "wiki_matched_official_cards":sum(c["official_name_match"] for c in data["wiki_candidates"]),
            "official_evolution_pages":len(data["official_evolution_pages"]),
            "official_level_entries":sum(len(p["levels"]) for p in data["official_evolution_pages"]),
            "conflict_counts":dict(Counter(c["kind"] for c in data["conflicts"])),
            "wiki_gap_cards":gaps,
            "unresolved_wiki_gap_cards":[c for c in gaps if c["url"] not in verified_urls],
            "limits":data["limits"]}


def preferred_levels(data,card):
    official=next((p for p in data["official_evolution_pages"] if p["url"]==card["source"]["url"]),None)
    if official:
        levels=[]
        for raw in official["levels"]:
            locked=raw["ability_unlock_level"] is not None
            levels.append({**raw,"ability_label":raw["ability"],
                           "ability":"No Ability" if locked else raw["ability"],
                           "verification":"official_table_observed"})
        return {"source_kind":"official","source_url":official["url"],"levels":levels}
    wiki=next((w for w in data["wiki_candidates"] if normalize(w["name"])==normalize(card["name"])),None)
    if not wiki:
        return {"source_kind":"official_maximum_only","source_url":card["source"]["url"],"levels":[card]}
    levels=[]
    for raw in wiki["levels"]:
        unlock=wiki["ability_unlock_level"]
        ability=("No Ability" if wiki["ability"].lower() in {"none","no ability"} or
                 (unlock is not None and raw["level"]<unlock) else
                 wiki["ability"] if unlock is not None and wiki["ability"] else None)
        levels.append({**raw,"ability":ability,"bonus":wiki["bonus"] or None,
                       "verification":"wiki_candidate","ability_unlock_level":unlock})
    return {"source_kind":"wiki_candidate","source_url":wiki["source"]["url"],"levels":levels}


def lookup_reference(name):
    data=json.loads((Path(__file__).parent/"data/card_reference.json").read_text(encoding="utf-8"))
    key=normalize(name)
    official_pages=[p for p in data["official_evolution_pages"] if any(normalize(c["name"])==key for c in p["levels"])]
    maximum=next((c for c in data["official_maximum_levels"] if normalize(c["name"])==key),None)
    return {"query":name,
            "official_maximum_levels":[c for c in data["official_maximum_levels"] if normalize(c["name"])==key],
            "official_evolution_pages":official_pages,
            "preferred_level_source":"official" if official_pages else "wiki_candidate",
            "preferred_levels":preferred_levels(data,maximum) if maximum else None,
            "wiki_candidates":[c for c in data["wiki_candidates"] if normalize(c["name"])==key],
            "conflicts":[c for c in data["conflicts"] if normalize(c["name"])==key],
            "limits":data["limits"]}


if __name__=="__main__":
    data=build_reference()
    output=Path(__file__).parent/"data"/"card_reference.json"
    output.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    report=reference_report(data)
    report_path=Path("local/reference-coverage.json")
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in {"wiki_gap_cards","unresolved_wiki_gap_cards","limits"}},indent=2))
