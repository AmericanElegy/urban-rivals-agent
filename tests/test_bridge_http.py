"""Optional real loopback integration test; runs when OCR dependencies exist."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@unittest.skipUnless(importlib.util.find_spec("rapidocr_onnxruntime"),"OCR extra not installed")
class BridgeHTTPTests(unittest.TestCase):
    def test_auth_freshness_and_duplicate_frame(self):
        from PIL import Image
        with socket.socket() as probe:
            probe.bind(("127.0.0.1",0))
            port=probe.getsockname()[1]
        with tempfile.TemporaryDirectory() as directory:
            log_path=Path(directory)/"server.log"
            with log_path.open("w",encoding="utf-8") as log:
                process=subprocess.Popen([sys.executable,"-u","-m","urban_rivals","serve","--port",str(port),"--output",directory],stdout=log,stderr=log,cwd=Path(__file__).resolve().parents[1])
            try:
                token=None
                for _ in range(150):
                    token_path=Path(directory)/"pairing-token.txt"
                    if token_path.exists() and "Local OCR bridge:" in log_path.read_text(encoding="utf-8"):
                        token=token_path.read_text(encoding="utf-8")
                        break
                    if process.poll() is not None:
                        self.fail("OCR bridge failed to start; inspect its temporary log locally")
                    time.sleep(.1)
                self.assertIsNotNone(token,"Bridge startup timed out")
                endpoint=f"http://127.0.0.1:{port}"
                with urlopen(endpoint+"/health",timeout=5) as response:
                    self.assertFalse(json.load(response)["execute_enabled"])
                def post(data,authorization=None,origin=None):
                    headers={"Content-Type":"application/json"}
                    if authorization:
                        headers["Authorization"]="Bearer "+authorization
                    if origin:
                        headers["Origin"]=origin
                    request=Request(endpoint+"/step",data=json.dumps(data).encode(),headers=headers)
                    return urlopen(request,timeout=15)
                with self.assertRaises(HTTPError) as failure:
                    post({})
                self.assertEqual(failure.exception.code,401)
                with self.assertRaises(HTTPError) as failure:
                    post({},token,"https://evil.test")
                self.assertEqual(failure.exception.code,403)
                stream=io.BytesIO()
                Image.new("RGB",(1318,744)).save(stream,format="PNG")
                frame=dict(schema="urban-rivals/frame/v1",url="https://www.urban-rivals.com/game/play/webgl/",
                           captured_at=time.time(),sequence=1,run_id="test-run-identity-0001",mode="training",execute=False,
                           png=base64.b64encode(stream.getvalue()).decode())
                with post(frame,token) as response:
                    result=json.load(response)
                self.assertIsNone(result["action"])
                self.assertTrue(result["stop"])
                self.assertIn("offline",result["status"])
                with self.assertRaises(HTTPError) as failure:
                    post(frame,token)
                self.assertEqual(failure.exception.code,422)
            finally:
                if token and process.poll() is None:
                    request=Request(f"http://127.0.0.1:{port}/shutdown",data=b"{}",
                                    headers={"Content-Type":"application/json","Authorization":"Bearer "+token})
                    with urlopen(request,timeout=5):
                        pass
                    process.wait(timeout=5)
                elif process.poll() is None:
                    # Kill only this test's own process tree if startup failed.
                    if sys.platform=="win32":
                        subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True)
                    else:
                        process.terminate()
                    process.wait(timeout=5)
