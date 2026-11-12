import test from "node:test";
import assert from "node:assert/strict";

test("popup remembers pairing in memory but never restores automatic execution",async()=>{
  const controls=new Map();
  for(const id of ["status","start","stop","token","execute"]){
    controls.set(id,{value:"",checked:false,textContent:"",disabled:false,listeners:{},
      addEventListener(event,handler){this.listeners[event]=handler;}});
  }
  const saved={pairingToken:"test-token-"+"x".repeat(40)};
  let request;
  globalThis.document={getElementById:id=>controls.get(id)};
  globalThis.chrome={storage:{session:{get:async()=>saved,set:async values=>Object.assign(saved,values)}},
    runtime:{sendMessage:async message=>{if(message.type==="start")request=message;return {status:"test"};}}};
  const oldInterval=globalThis.setInterval;
  globalThis.setInterval=()=>0;
  try{
    await import("./popup.js");
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(controls.get("token").value,saved.pairingToken);
    assert.equal(controls.get("execute").checked,false);
    assert.equal(controls.get("start").textContent,"Capture one frame");
    await controls.get("start").listeners.click();
    assert.equal(request.execute,false);
    controls.get("execute").checked=true;
    controls.get("execute").listeners.change();
    assert.equal(controls.get("start").textContent,"Start automatic play");
    controls.get("token").value="";
    await controls.get("token").listeners.change();
    assert.equal(saved.pairingToken,"");
  }finally{globalThis.setInterval=oldInterval;}
});


test("an older loaded manifest without storage does not break Start",async()=>{
  const controls=new Map();
  for(const id of ["status","start","stop","token","execute"]){
    controls.set(id,{value:"",checked:false,textContent:"",disabled:false,listeners:{},
      addEventListener(event,handler){this.listeners[event]=handler;}});
  }
  let started=false;
  globalThis.document={getElementById:id=>controls.get(id)};
  globalThis.chrome={runtime:{sendMessage:async message=>{started ||= message.type==="start";return {status:"Connected"};}}};
  const oldInterval=globalThis.setInterval;
  globalThis.setInterval=()=>0;
  try{
    await import("./popup.js?old-manifest");
    controls.get("token").value="test-"+"x".repeat(40);
    await controls.get("start").listeners.click();
    assert.equal(started,true);
    assert.equal(controls.get("status").textContent,"Connected");
  }finally{globalThis.setInterval=oldInterval;}
});


test("status polling cannot erase a local token validation error",async()=>{
  const controls=new Map();
  for(const id of ["status","start","stop","token","execute"]){
    controls.set(id,{value:"",checked:false,textContent:"",disabled:false,listeners:{},
      addEventListener(event,handler){this.listeners[event]=handler;}});
  }
  let poll,started=false;
  globalThis.document={getElementById:id=>controls.get(id)};
  globalThis.chrome={runtime:{sendMessage:async message=>{
    started ||= message.type==="start";return {status:"Not started"};}}};
  const oldInterval=globalThis.setInterval;
  globalThis.setInterval=fn=>{poll=fn;return 0;};
  try{
    await import("./popup.js?sticky-error");
    controls.get("token").value="x".repeat(40)+"\u200b";
    await controls.get("start").listeners.click();
    poll();
    await new Promise(resolve=>setImmediate(resolve));
    assert.match(controls.get("status").textContent,/Invalid token characters/);
    assert.equal(started,false);
  }finally{globalThis.setInterval=oldInterval;}
});


test("automatic startup closes the popup only after a successful connection",async()=>{
  const controls=new Map();
  for(const id of ["status","start","stop","token","execute"]){
    controls.set(id,{value:"",checked:false,textContent:"",disabled:false,listeners:{},
      addEventListener(event,handler){this.listeners[event]=handler;}});
  }
  let closed=0,result={error:"Input attachment failed"};
  globalThis.document={getElementById:id=>controls.get(id)};
  globalThis.window={close:()=>{closed++;}};
  globalThis.chrome={runtime:{sendMessage:async message=>message.type==="start"?result:{status:"Not started"}}};
  const oldInterval=globalThis.setInterval;
  globalThis.setInterval=()=>0;
  try{
    await import("./popup.js?automatic-focus-release");
    controls.get("token").value="x".repeat(43);
    controls.get("execute").checked=true;
    await controls.get("start").listeners.click();
    assert.equal(closed,0);
    result={status:"Connected; waiting for the first capture"};
    await controls.get("start").listeners.click();
    assert.equal(closed,1);
  }finally{globalThis.setInterval=oldInterval;}
});
