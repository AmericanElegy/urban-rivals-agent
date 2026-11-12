import test from "node:test";
import assert from "node:assert/strict";

test("popup-started inspect run captures one frame with unfocused parent window and no debugger",async()=>{
  let listener;
  let debuggerCalls=0;
  let captures=0;
  let posted=0;
  let stopped=0;
  const url="https://www.urban-rivals.com/game/play/webgl/";
  const tab={id:7,windowId:9,active:true,url};
  const g={x:100,y:100,width:1000,height:562,viewportWidth:1920,viewportHeight:900};
  globalThis.chrome={
    tabs:{query:async()=>[tab],get:async()=>tab,captureVisibleTab:async windowId=>{
      assert.equal(windowId,9);captures++;return "data:image/png;base64,cGl4ZWxz";
    }},
    windows:{get:async()=>({focused:false})},
    scripting:{executeScript:async()=>[{result:g}]},
    debugger:{attach:async()=>{debuggerCalls++;},detach:async()=>{debuggerCalls++;},sendCommand:async()=>{debuggerCalls++;},onDetach:{addListener:()=>{}}},
    runtime:{getURL:path=>"chrome-extension://test/"+path,onMessage:{addListener:handler=>{listener=handler;}}}
  };
  globalThis.fetch=async(endpoint,options)=>{
    if(endpoint.endsWith("/ready"))return {ok:true,json:async()=>({execute_enabled:false})};
    if(endpoint.endsWith("/step")){
      const frame=JSON.parse(options.body);
      assert.equal(frame.execute,false);
      assert.equal(frame.png,"cGl4ZWxz");
      posted++;
      return {ok:true,json:async()=>({status:"Canvas captured locally; inspect offline",action:null,stop:true})};
    }
    if(endpoint.endsWith("/stop")){stopped++;return {ok:true};}
    throw new Error("Unexpected network destination");
  };
  await import("./worker.js");
  const started=await new Promise(resolve=>listener({type:"start",token:"x".repeat(43),execute:false},{url:"chrome-extension://test/popup.html"},resolve));
  assert.match(started.status,/Connected/);
  for(let i=0;i<20&&!stopped;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(captures,1);
  assert.equal(posted,1);
  assert.equal(stopped,1);
  assert.equal(debuggerCalls,0);
  const result=await new Promise(resolve=>listener({type:"status"},{url:"chrome-extension://test/popup.html"},resolve));
  assert.match(result.status,/captured locally/);
  assert.match(result.status,/automatic play is OFF/);
});


test("execution refuses an outdated bridge before attaching game input",async()=>{
  let listener;
  let attached=0;
  globalThis.chrome={
    tabs:{query:async()=>[{id:7,url:"https://www.urban-rivals.com/game/play/webgl/"}]},
    debugger:{attach:async()=>{attached++;},onDetach:{addListener:()=>{}}},
    runtime:{getURL:path=>"chrome-extension://test/"+path,onMessage:{addListener:fn=>{listener=fn;}}}
  };
  globalThis.fetch=async()=>({ok:true,json:async()=>({execute_enabled:true})});
  await import("./worker.js?outdated-bridge-test");
  const result=await new Promise(resolve=>listener({type:"start",token:"x".repeat(43),execute:true},
    {url:"chrome-extension://test/popup.html"},resolve));
  assert.match(result.error,/Restart the local bridge/);
  assert.equal(attached,0);
});


test("an unreachable bridge explains how to restore the local service",async()=>{
  let listener;
  globalThis.chrome={tabs:{query:async()=>[{id:7,url:"https://www.urban-rivals.com/game/play/webgl/"}]},
    debugger:{onDetach:{addListener:()=>{}}},runtime:{getURL:path=>"chrome-extension://test/"+path,
      onMessage:{addListener:fn=>{listener=fn;}}}};
  globalThis.fetch=async()=>{throw new TypeError("Failed to fetch");};
  await import("./worker.js?unreachable-bridge");
  const result=await new Promise(resolve=>listener({type:"start",token:"x".repeat(43),execute:true},
    {url:"chrome-extension://test/popup.html"},resolve));
  assert.match(result.error,/Local bridge is unavailable/);
  assert.match(result.error,/ReusePairingToken/);
});
