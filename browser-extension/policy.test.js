import test from "node:test";
import assert from "node:assert/strict";
import {allowedURL,validateAction,validateTarget} from "./policy.js";

test("only the exact official WebGL URL is eligible",()=>{
  assert.equal(allowedURL("https://www.urban-rivals.com/game/play/webgl/"),true);
  for(const u of ["https://evil.test/game/play/webgl/","http://www.urban-rivals.com/game/play/webgl/","https://www.urban-rivals.com/market/","https://www.urban-rivals.com.evil.test/game/play/webgl/","https://www.urban-rivals.com/game/play/webgl/?target=other"]){
    assert.equal(allowedURL(u),false);
  }
});
test("inspect may capture its selected game tab while popup has window focus",()=>{
  const tab={active:true,url:"https://www.urban-rivals.com/game/play/webgl/"};
  assert.equal(validateTarget(tab,{focused:false},false),tab);
});
test("live clicks still require the game window to be focused",()=>{
  const tab={active:true,url:"https://www.urban-rivals.com/game/play/webgl/"};
  assert.throws(()=>validateTarget(tab,{focused:false},true),/live input stopped/);
  assert.equal(validateTarget(tab,{focused:true},true),tab);
});
test("inspect still rejects navigation or a different selected tab",()=>{
  assert.throws(()=>validateTarget({active:false,url:"https://www.urban-rivals.com/game/play/webgl/"},{focused:false},false));
  assert.throws(()=>validateTarget({active:true,url:"https://example.com/"},{focused:false},false));
});
test("actions are fresh, bounded and bound to the exact frame",()=>{
  const frame={sequence:3,run_id:"run",captured_at:Date.now()/1000};
  const result={sequence:3,run_id:"run",action:{type:"click",x:.5,y:.6}};
  assert.deepEqual(validateAction(result,frame),result.action);
  for(const bad of [{...result,sequence:2},{...result,run_id:"other"},{...result,action:{type:"click",x:2,y:.5}},{...result,action:{type:"click",x:NaN,y:.5}},{...result,action:{type:"navigate",x:.5,y:.5}}]){
    assert.throws(()=>validateAction(bad,frame));
  }
  assert.throws(()=>validateAction(result,{...frame,captured_at:Date.now()/1000-15}));
});
