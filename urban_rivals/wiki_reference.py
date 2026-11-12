"""Resumable public wiki acquisition. Reference facts never enable live actions."""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API="https://urban-rivals.fandom.com/api.php"


def collect(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    continuation={}
    index=0
    pages=0
    while True:
        path=output/f"batch-{index:04d}.json"
        if path.exists():
            result=json.loads(path.read_text(encoding="utf-8"))
        else:
            params={"action":"query","format":"json","generator":"allpages",
                    "gapnamespace":0,"gaplimit":50,"prop":"revisions",
                    "rvprop":"ids|timestamp|content","rvslots":"main",**continuation}
            request=Request(API+"?"+urlencode(params),headers={
                "User-Agent":"UrbanRivalsReference/0.1 (public card-fact research)"})
            with urlopen(request,timeout=40) as response:
                result=json.load(response)
            if "error" in result:
                raise ValueError(result["error"])
            if "query" not in result:
                raise ValueError("Wiki returned no query data; preserve cache and investigate")
            path.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
            time.sleep(.25)
        pages+=len(result.get("query",{}).get("pages",{}))
        print(f"Cached batch {index}: {pages} public pages",flush=True)
        if "continue" not in result:
            return {"pages":pages,"batches":index+1,"complete":True}
        continuation=result["continue"]
        index+=1


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default="local/wiki-reference-cache")
    args=parser.parse_args()
    print(json.dumps(collect(args.output)))
