import {allowedURL,validateAction,validateTarget} from "./policy.js";
const ENDPOINT="http://127.0.0.1:8876";
let run=null;
let status="Not started";
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const bounded=async(promise,label,ms=4000)=>{
  let timer;
  try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(label+" timed out; stopped")),ms);})]);}
  finally{clearTimeout(timer);}
};

async function stop(reason="Stopped"){
  const old=run;run=null;status=reason;
  if(old){
    if(old.execute)try{await chrome.debugger.detach({tabId:old.tabId});}catch{}
    try{await fetch(ENDPOINT+"/stop",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+old.token},body:JSON.stringify({run_id:old.id}),signal:AbortSignal.timeout(2000)});}catch{}
  }
}

async function geometry(tabId){
  const results=await bounded(chrome.scripting.executeScript({target:{tabId},func:()=>{
    const canvas=document.getElementById("unity-canvas");
    if(!canvas||document.visibilityState!=="visible")return null;
    const r=canvas.getBoundingClientRect();
    return {x:r.x,y:r.y,width:r.width,height:r.height,pageX:r.x+scrollX,pageY:r.y+scrollY,viewportWidth:innerWidth,viewportHeight:innerHeight};
  }}),"Canvas geometry");
  const g=results[0]?.result;
  if(!g||g.width<640||g.height<320||g.x<0||g.y<0||g.x+g.width>g.viewportWidth+1||g.y+g.height>g.viewportHeight+1)throw new Error("The full Unity canvas must be visible and at least 640 pixels wide");
  return g;
}

async function currentTab(activeRun){
  const tab=await chrome.tabs.get(activeRun.tabId);
  const window=await chrome.windows.get(tab.windowId);
  return validateTarget(tab,window,activeRun.execute);
}

async function loop(activeRun){
  try{
    while(run===activeRun){
      if(Date.now()-activeRun.started>15*60*1000)throw new Error("15-minute session limit reached");
      status="Checking the active game tab…";
      const tab=await bounded(currentTab(activeRun),"Active game tab");
      const g=await geometry(tab.id);
      const captured_at=Date.now()/1000;
      status="Capturing visible game pixels…";
      const screenshot=await bounded(chrome.tabs.captureVisibleTab(tab.windowId,{format:"png"}),"Visible-tab capture");
      if(run!==activeRun)return;
      await currentTab(activeRun);
      if(JSON.stringify(await geometry(tab.id))!==JSON.stringify(g))throw new Error("Canvas moved during capture");
      const frame={schema:"urban-rivals/frame/v1",url:tab.url,mode:"training",execute:activeRun.execute,run_id:activeRun.id,sequence:++activeRun.sequence,captured_at,png:screenshot.replace(/^data:image\/png;base64,/,""),geometry:g};
      status="Reading the captured board locally…";
      const response=await fetch(ENDPOINT+"/step",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+activeRun.token},body:JSON.stringify(frame),signal:AbortSignal.timeout(12000)});
      const result=await response.json();
      if(run!==activeRun)return;
      if(!response.ok||result.stop)throw new Error(result.error||result.status||"Bridge stopped");
      status=result.status||"Reading canvas";
      const action=validateAction(result,frame);
      if(action){
        if(!activeRun.execute)throw new Error("Inspect mode received a click");
        await currentTab(activeRun);
        const now=await geometry(tab.id);
        if(JSON.stringify(now)!==JSON.stringify(g))throw new Error("Canvas moved during recognition");
        if(run!==activeRun)return;
        const point={x:g.x+action.x*g.width,y:g.y+action.y*g.height,button:"left",clickCount:1};
        // One command per response; no retry after an uncertain input outcome.
        await chrome.debugger.sendCommand({tabId:tab.id},"Input.dispatchMouseEvent",{type:"mousePressed",...point});
        await chrome.debugger.sendCommand({tabId:tab.id},"Input.dispatchMouseEvent",{type:"mouseReleased",...point});
      }
      await delay(650);
    }
  }catch(error){if(run===activeRun)await stop(error.message);}
}

chrome.debugger.onDetach.addListener(source=>{
  if(run?.execute&&run.tabId===source.tabId)void stop("Browser debugging connection ended");
});
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(message.type==="escape"&&sender.tab?.id===run?.tabId){void stop("Stopped with Escape");return;}
  if(sender.url!==chrome.runtime.getURL("popup.html"))return false;
  if(message.type==="status"){reply({status});return false;}
  if(message.type==="stop"){stop().then(()=>reply({status}));return true;}
  if(message.type!=="start")return false;
  (async()=>{
    if(run)throw new Error("Stop the current run before starting again");
    if(typeof message.token!=="string"||message.token.length<32||typeof message.execute!=="boolean")throw new Error("Paste the local pairing token first");
    const tabs=await chrome.tabs.query({active:true,currentWindow:true});
    const tab=tabs[0];
    if(!tab?.id||!allowedURL(tab.url))throw new Error("Open the Urban Rivals WebGL game tab");
    status="Checking local pairing and server mode…";
    const ping=await fetch(ENDPOINT+"/ready",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+message.token},body:"{}",signal:AbortSignal.timeout(4000)});
    const ready=await ping.json();
    if(!ping.ok)throw new Error(ready.error||"Pairing failed");
    if(message.execute&&!ready.execute_enabled)throw new Error("Server is inspect-only. Uncheck automatic play before Start.");
    const activeRun={id:crypto.randomUUID(),tabId:tab.id,token:message.token,execute:message.execute,sequence:0,started:Date.now()};
    if(activeRun.execute)await bounded(chrome.debugger.attach({tabId:tab.id},"1.3"),"Input connection");
    try{
      await geometry(tab.id);
      await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{
        if(document.documentElement.dataset.urbanRivalsEscape)return;
        document.documentElement.dataset.urbanRivalsEscape="1";
        document.addEventListener("keydown",event=>{if(event.key==="Escape")chrome.runtime.sendMessage({type:"escape"}).catch(()=>{});},true);
      }});
    }catch(error){if(activeRun.execute)await chrome.debugger.detach({tabId:tab.id});throw error;}
    run=activeRun;status="Connected; waiting for the first capture";
    reply({status});void loop(activeRun);
  })().catch(error=>{status=error.message;reply({error:status});});
  return true;
});
