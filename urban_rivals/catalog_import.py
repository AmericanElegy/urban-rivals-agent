"""Conservative import of card facts read from rendered official card pages."""
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .engine import Card, parse_effect
from .vision import normalize
from .card_text import annotate


def merge_official_records(catalog,records):
    """Keep source text intact; unsupported effects never enter the catalog.

    Existing reference evolutions remain first. An identical stat/level key with
    different mechanics is quarantined, never overwritten by a new source.
    """
    merged=dict(catalog,cards=list(catalog["cards"]))
    identities={}
    def identity(raw):
        return (normalize(raw["name"]),raw["power"],raw["damage"],raw["stars"])
    def parsed(raw):
        return Card(raw["name"],raw["power"],raw["damage"],raw["stars"],raw["clan"],
                    parse_effect(raw.get("ability","")),parse_effect(raw.get("bonus","")))
    for raw in merged["cards"]:
        identities[identity(raw)]=parsed(raw)
    audit=[]
    for source in records:
        entry={"source":source.get("url"),"name":source.get("name")}
        try:
            url=urlparse(source.get("url",""))
            if (url.scheme,url.netloc,url.path)!=("https","www.urban-rivals.com","/game/characters/") or not parse_qs(url.query).get("id_perso",[""])[0].isdigit():
                raise ValueError("Not an official character source URL")
            raw={key:source[key] for key in ("name","power","damage","stars","clan","ability","bonus")}
            if any(type(raw[k]) is not int for k in ("power","damage","stars")):
                raise ValueError("Stats and stars must be integers")
            for field in ("ability","bonus"):
                raw[field]=annotate(raw[field],raw["clan"],source.get("url"),field)
            card=parsed(raw)
            key=identity(raw)
            if key in identities:
                if identities[key]!=card:
                    raise ValueError("Conflicting existing evolution; retain original and review")
                entry["result"]="existing"
            else:
                identities[key]=card
                merged["cards"].append(raw)
                entry["result"]="added"
            entry["card"]=raw
        except (ValueError,KeyError,TypeError) as error:
            entry.update(result="rejected",reason=str(error),record=source)
        audit.append(entry)
    return merged,audit


def refresh_catalog():
    """Re-evaluate the retained official facts after parser improvements."""
    data_path=Path(__file__).parent/"data"
    catalog_path=data_path/"training_cards.json"
    audit_path=data_path/"official_catalog_import.json"
    catalog=json.loads(catalog_path.read_text(encoding="utf-8"))
    source=json.loads(audit_path.read_text(encoding="utf-8"))
    records=[]
    for entry in source["entries"]:
        record=dict(entry.get("card",entry.get("record")))
        record["url"]=entry["source"]
        records.append(record)
    merged,first_audit=merge_official_records(catalog,records)
    added=sum(e["result"]=="added" for e in first_audit)
    # Audit the final catalog so a second refresh produces identical files.
    final_catalog,final_audit=merge_official_records(merged,records)
    if final_catalog!=merged:
        raise RuntimeError("Catalog refresh was not idempotent")
    catalog_path.write_text(json.dumps(merged,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    audit_path.write_text(json.dumps({"source":source["source"],"entries":final_audit},
                                     indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return {"newly_supported_records":added,"catalog_evolutions":len(merged["cards"]),
            "parsed_source_records":sum(e["result"]!="rejected" for e in final_audit)}


if __name__=="__main__":
    print(json.dumps(refresh_catalog(),indent=2))
