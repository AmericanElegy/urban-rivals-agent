"""Authenticated loopback-only OCR bridge for the opt-in Chrome extension."""
import base64
import binascii
import io
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .vision import VisionSession, RecognitionError
from .mode_policy import VALID_MODES
from .calibration import load_calibration, save_calibration

SCHEMA="urban-rivals/frame/v1"
MAX_BODY=8*1024*1024


def crop_viewport(image,geometry):
    if geometry is None:
        return image
    if not isinstance(geometry,dict):
        raise ValueError("Invalid viewport geometry")
    names=("x","y","width","height","viewportWidth","viewportHeight")
    import math
    if any(type(geometry.get(n)) not in (int,float) or not math.isfinite(geometry[n]) for n in names):
        raise ValueError("Incomplete viewport geometry")
    x,y,w,h,vw,vh=(geometry[n] for n in names)
    if vw<640 or vh<320 or x<0 or y<0 or w<640 or h<320 or x+w>vw+1 or y+h>vh+1:
        raise ValueError("Canvas is not fully visible")
    sx,sy=image.width/vw,image.height/vh
    if not .5<=sx<=4 or abs(sx-sy)>.02:
        raise ValueError("Screenshot/viewport scale disagreement")
    return image.crop((round(x*sx),round(y*sy),round((x+w)*sx),round((y+h)*sy)))


def validate_frame(data, now=None):
    if data.get("schema")!=SCHEMA:
        raise ValueError("Unknown frame schema")
    url=urlparse(data.get("url",""))
    if (url.scheme,url.netloc,url.path)!=("https","www.urban-rivals.com","/game/play/webgl/"):
        raise ValueError("Only the Urban Rivals browser game is allowed")
    if "focus_resumed" in data and type(data["focus_resumed"]) is not bool:
        raise ValueError("Invalid focus-resume flag")
    timestamp=data.get("captured_at")
    if type(timestamp) not in (int,float) or not 0 <= (now or time.time())-timestamp <= 10:
        raise ValueError("Frame timestamp is stale or in the future")
    if type(data.get("sequence")) is not int or data["sequence"]<1:
        raise ValueError("Invalid frame sequence")
    if not isinstance(data.get("run_id"),str) or not 16<=len(data["run_id"])<=80:
        raise ValueError("Missing run identity")
    if data.get("mode") not in VALID_MODES:
        raise ValueError(f"Unsupported mode: expected one of {VALID_MODES}")
    if type(data.get("execute")) is not bool:
        raise ValueError("Missing explicit inspect/execute mode")
    if "advisor" in data and type(data["advisor"]) is not bool:
        raise ValueError("Invalid advisor flag")


def serve(host="127.0.0.1",port=8876,execute=False,output="local",session_factory=VisionSession,reuse_token=False):
    if host!="127.0.0.1":
        raise ValueError("Bridge must bind to 127.0.0.1")
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    token=secrets.token_urlsafe(32)
    if reuse_token:
        token=(output/"pairing-token.txt").read_text(encoding="utf-8").strip()
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}",token):
            raise ValueError("Existing pairing token is invalid")
    (output/"pairing-token.txt").write_text(token,encoding="utf-8")
    sessions={}
    stopped=set()
    sequences={}
    expected_host=f"127.0.0.1:{port}"
    from .engine import ENGINE_REVISION
    shared_ocr=None
    shared_catalog=None
    if session_factory is VisionSession:
        from .vision import LocalOCR, Catalog
        from PIL import Image
        shared_ocr=LocalOCR()
        shared_ocr.text(Image.new("RGB",(640,360)),(0,0,1,1))
        shared_catalog=Catalog(allow_star_fallback=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # Never log Authorization headers or pairing tokens.

        def send(self,status,data):
            payload=json.dumps(data).encode()
            self.send_response(status)
            origin=self.headers.get("Origin","")
            if origin.startswith("chrome-extension://"):
                self.send_header("Access-Control-Allow-Origin",origin)
                self.send_header("Vary","Origin")
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_OPTIONS(self):
            if self.headers.get("Host")!=expected_host or not self.headers.get("Origin","").startswith("chrome-extension://"):
                return self.send(403,{"error":"Origin is not an extension"})
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin",self.headers["Origin"])
            self.send_header("Access-Control-Allow-Methods","POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers","Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Private-Network","true")
            self.end_headers()

        def do_GET(self):
            if self.headers.get("Host")!=expected_host:
                return self.send(403,{"error":"Invalid host"})
            if self.path=="/calibrate":
                return self.send(200,{"points":load_calibration(output/"calibration.json")})
            self.send(200 if self.path=="/health" else 404,
                      {"service":"urban-rivals-local-bridge","execute_enabled":execute,"engine_revision":ENGINE_REVISION,"modes":list(VALID_MODES)})

        def do_POST(self):
            if self.headers.get("Host")!=expected_host:
                return self.send(403,{"error":"Invalid host"})
            authorization=self.headers.get("Authorization","")
            if not secrets.compare_digest(authorization,"Bearer "+token):
                return self.send(401,{"error":"Invalid local pairing token"})
            origin=self.headers.get("Origin","")
            if origin and not origin.startswith("chrome-extension://"):
                return self.send(403,{"error":"Website origins cannot control the bridge"})
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 0<length<=MAX_BODY:
                    raise ValueError("Frame is missing or too large")
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):
                    raise ValueError("Expected a JSON object")
                if self.path=="/ready":
                    with (output/"receipts.jsonl").open("a",encoding="utf-8") as stream:
                        stream.write(json.dumps({"time":time.time(),"event":"ready",
                            "requested_execute":data.get("execute"),"server_execute":execute,
                            "engine_revision":ENGINE_REVISION})+"\n")
                    return self.send(200,{"execute_enabled":execute,"capture":"visible-tab-v1","engine_revision":ENGINE_REVISION})
                if self.path=="/shutdown":
                    self.send(200,{"status":"Bridge shutting down"})
                    from threading import Thread
                    Thread(target=server.shutdown,daemon=True).start()
                    return
                if self.path=="/stop":
                    run_id=data.get("run_id")
                    if isinstance(run_id,str):
                        stopped.add(run_id)
                        sessions.pop(run_id,None)
                    return self.send(200,{"status":"Stopped"})
                if self.path=="/calibrate":
                    points=save_calibration(output/"calibration.json",data)
                    return self.send(200,{"status":"Calibration saved","points":points})
                if self.path!="/step":
                    return self.send(404,{"error":"Unknown endpoint"})
                validate_frame(data)
                run_id=data["run_id"]
                if run_id in stopped:
                    raise ValueError("Run stopped; click Start to create a new run")
                if data["sequence"]<=sequences.get(run_id,0):
                    raise ValueError("Duplicate or out-of-order frame")
                sequences[run_id]=data["sequence"]
                if run_id not in sessions:
                    if sessions:
                        raise ValueError("Stop the previous run before starting another")
                    is_exec = execute and data["execute"]
                    is_advisor = bool(data.get("advisor", False)) and not is_exec
                    if session_factory is VisionSession and not is_exec and not is_advisor:
                        from types import SimpleNamespace
                        sessions[run_id]=SimpleNamespace(execute=False, advisor=False)
                    elif shared_ocr is not None:
                        from .vision import CanvasReader
                        sessions[run_id]=session_factory(reader=CanvasReader(ocr=shared_ocr,catalog=shared_catalog),execute=is_exec,mode=data["mode"],advisor=is_advisor)
                    else:
                        if session_factory is VisionSession:
                            sessions[run_id]=session_factory(execute=is_exec,mode=data["mode"],advisor=is_advisor)
                        else:
                            sessions[run_id]=session_factory(execute=is_exec)
                session=sessions[run_id]
                if session.execute!=(execute and data["execute"]):
                    raise ValueError("Cannot change inspect/execute mode mid-run")
                from PIL import Image
                Image.MAX_IMAGE_PIXELS=12_000_000
                raw=base64.b64decode(data.get("png",""),validate=True)
                if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Expected a PNG canvas capture")
                image=Image.open(io.BytesIO(raw))
                if image.width>8192 or image.height>4608 or image.width*image.height>12_000_000:
                    raise ValueError("Viewport screenshot is too large")
                image=crop_viewport(image,data.get("geometry"))
                w,h=image.size
                if not 640<=w<=4096 or not 320<=h<=2304 or not 1.7<=w/h<=1.85:
                    raise ValueError("Unexpected canvas size/aspect ratio; stop and recalibrate")
                reader=getattr(session,"reader",None)
                if reader is not None and hasattr(reader,"set_canvas_css_width"):
                    reader.set_canvas_css_width(data.get("geometry",{}).get("width",image.width))
                image=image.convert("RGB").resize((1318,744))
                image.save(output/"latest-canvas.png")
                (output/"latest-geometry.json").write_text(json.dumps(data.get("geometry")),encoding="utf-8")
                if session.execute and data.get("focus_resumed"):
                    session.reset_stability()
                result=(session.step(image) if (session.execute or getattr(session,"advisor",False)) else
                        {"status":"Canvas captured locally; inspect offline without a turn timer", "action":None,"stop":True})
                # OCR/search may have taken too long. A late action is never sent.
                elapsed=time.time()-data["captured_at"]
                if result.get("action") is not None and elapsed>20:
                    raise RecognitionError("OCR/search exceeded the 20-second frame deadline")
                if elapsed>25:
                    raise RecognitionError("OCR/search exceeded the 25-second frame deadline")
                result.update({"sequence":data["sequence"],"run_id":run_id})
                with (output/"receipts.jsonl").open("a",encoding="utf-8") as stream:
                    stream.write(json.dumps({"time":time.time(),**result})+"\n")
                if result.get("stop"):
                    stopped.add(run_id)
                    sessions.pop(run_id,None)
                self.send(200,result)
            except (ValueError,TypeError,KeyError,OSError,binascii.Error) as error:
                run_id=data.get("run_id") if isinstance(locals().get("data"),dict) else None
                if run_id:
                    stopped.add(run_id)
                    sessions.pop(run_id,None)
                result={"error":str(error),"stop":True}
                try:
                    with (output/"receipts.jsonl").open("a",encoding="utf-8") as stream:
                        stream.write(json.dumps({"time":time.time(),"run_id":run_id,**result})+"\n")
                except OSError:
                    pass
                self.send(422,result)
            except Exception as error:
                # Unexpected OCR/runtime errors must also stop, never trigger a retry.
                if isinstance(locals().get("data"),dict):
                    stopped.add(data.get("run_id"))
                    sessions.pop(data.get("run_id"),None)
                self.send(500,{"error":f"Local OCR/runtime failed: {type(error).__name__}","stop":True})

    server=HTTPServer((host,port),Handler)
    server.timeout=1
    print(f"Local OCR bridge: http://{expected_host}",flush=True)
    print(f"Pairing token saved locally: {(output/'pairing-token.txt').resolve()}",flush=True)
    print(f"Mode: {'execution permitted; extension must also opt in' if execute else 'INSPECT ONLY; no clicks'}",flush=True)
    try:
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
