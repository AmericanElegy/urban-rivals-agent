"""Labeled, offline OCR replay. Does not open a browser or send game inputs."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import time
from .vision import CanvasReader,normalize


def compare_report(actual,frame,hands):
    checks=[]
    def check(group,field,expected,value):
        same=normalize(value)==normalize(expected) if isinstance(expected,str) and isinstance(value,str) else value==expected
        checks.append({"group":group,"field":field,"expected":expected,"actual":value,
                       "result":"pass" if same else "unreadable" if value is None or value=="" else "wrong"})
    check("phase","phase",frame["phase"],actual.get("phase"))
    if frame["phase"]!="round_board":
        return checks
    for key in ("round","seconds_left","observed_card"):
        # Missing is distinct from an intentionally null observed opponent card.
        check("board",key,frame[key],actual.get(key,"<missing>"))
    if "engine_ready" in frame:
        check("readiness","engine_ready",frame["engine_ready"],actual.get("engine_ready"))
    for key,expected in frame["resources"].items():
        check("resources",key,expected,actual.get("resources",{}).get(key))
    observed={(c["side"],c["slot"]):c for c in actual.get("cards",[])}
    for side in (0,1):
        for slot,(name,power,damage,stars) in enumerate(hands[side]):
            card=observed.get((side,slot),{})
            prefix=f"{side}:{slot}"
            check("cards",prefix+".name",name,card.get("name"))
            used=slot in frame["used"][side]
            check("played",prefix+".used",used,card.get("used"))
            if used:
                check("played",prefix+".paid_pillz",frame["spent"][prefix],card.get("paid_pillz"))
            else:
                for key,value in (("power",power),("damage",damage),("stars",stars)):
                    check("cards",prefix+"."+key,value,card.get(key))
    return checks


def replay(manifest_path,output_path="local/ocr-replay-report.json",root=".",reader=None):
    from PIL import Image
    manifest=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("schema")!="urban-rivals/ocr-replay/v1":
        raise ValueError("Unknown replay schema")
    reader=reader or CanvasReader()
    groups=defaultdict(Counter)
    cases=[]
    missing=[]
    root=Path(root)
    for frame in manifest["frames"]:
        path=root/frame["path"]
        if not path.exists() and frame.get("fallback_path"):
            path=root/frame["fallback_path"]
        if not path.exists():
            missing.append(str(path))
            continue
        image=Image.open(path).convert("RGB")
        if frame.get("crop"):
            image=image.crop(frame["crop"])
        for scale in frame.get("scales",[1]):
            resized=image.resize((round(image.width*scale),round(image.height*scale)))
            canonical=resized.resize((1318,744))
            start=time.perf_counter()
            actual=reader.diagnostics(canonical)
            checks=compare_report(actual,frame,manifest.get("hands",{}).get(frame.get("hands"),[]))
            for check in checks:
                groups[check["group"]][check["result"]]+=1
            print(f"Replay {frame['id']} scale={scale}: {sum(c['result']=='pass' for c in checks)}/{len(checks)} fields, {time.perf_counter()-start:.2f}s",flush=True)
            cases.append({"id":frame["id"],"scale":scale,"seconds":round(time.perf_counter()-start,3),
                          "passed":all(c["result"]=="pass" for c in checks),"checks":checks,"report":actual})
    result={"schema":"urban-rivals/ocr-replay-result/v1","cases":cases,"missing":missing,
            "groups":{g:dict(c) for g,c in groups.items()},"passed":not missing and bool(cases) and all(c["passed"] for c in cases),
            "limits":"Local source frames plus synthetic image resampling; not proof of live input, arbitrary layouts, or all card/rule support."}
    path=Path(output_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,ensure_ascii=True),encoding="utf-8")
    return result


def verify_match(manifest_path,output_path="local/match-verification.json",root=".",reader=None):
    """Exercise the real board reader and round-receipt reconciliation offline."""
    from PIL import Image
    from .engine import Move
    manifest=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("schema")!="urban-rivals/recorded-match/v1":
        raise ValueError("Unknown recorded-match schema")
    reader=reader or CanvasReader()
    previous=None
    cases=[]
    for frame in manifest["frames"]:
        start=time.perf_counter()
        try:
            image=Image.open(Path(root)/frame["path"]).convert("RGB")
            if frame.get("crop"):
                image=image.crop(frame["crop"])
            image=image.resize((1318,744))
            submitted=Move(**frame["submitted"]) if frame.get("submitted") else None
            board=reader.board(image,previous,submitted)
            if board is None:
                raise ValueError("Not a readable YOUR TURN board")
            state=board.state
            actual={"round":state.round,"leader":state.leader,"observed_card":board.observed_card,
                    "life":[p.life for p in state.players],"pillz":[p.pillz for p in state.players],
                    "used":[list(p.used) for p in state.players],
                    "last_won":[p.last_won for p in state.players],
                    "hands":[[c.name for c in p.hand] for p in state.players]}
            checks=[{"field":key,"expected":value,"actual":actual.get(key),
                     "passed":actual.get(key)==value} for key,value in frame["expected"].items()]
            case={"id":frame["id"],"passed":all(c["passed"] for c in checks),"checks":checks,
                  "seconds":round(time.perf_counter()-start,3)}
            previous=state
        except (ValueError,OSError) as error:
            case={"id":frame["id"],"passed":False,"error":str(error)}
        cases.append(case)
        print(f"Match {frame['id']}: {'pass' if case['passed'] else 'FAIL'}",flush=True)
        if not case["passed"]:
            break
    result={"schema":"urban-rivals/match-verification/v1","cases":cases,
            "passed":bool(cases) and len(cases)==len(manifest["frames"]) and all(c["passed"] for c in cases),
            "limits":"Offline board and receipt validation only; no capture transport, live clicks or complete automatic match is proven."}
    path=Path(output_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
