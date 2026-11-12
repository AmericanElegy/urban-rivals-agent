"""Conservative import of card facts read from rendered official card pages."""
from urllib.parse import urlparse, parse_qs
from .engine import Card, parse_effect
from .vision import normalize


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
            if raw["clan"] in {"GhosTown","Leader","Oculus"}:
                raise ValueError("Clock-specific, leader or infiltration rules require separately verified entries")
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
