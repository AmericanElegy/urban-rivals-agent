const status=document.getElementById("status");
const start=document.getElementById("start");
let starting=false;
const tokenField=document.getElementById("token");
const executeField=document.getElementById("execute");
// Memory-only extension session storage, never sync/local storage or game page DOM.
const sessionStore=chrome.storage?.session;
if(sessionStore)sessionStore.get("pairingToken").then(saved=>{
  if(!tokenField.value&&typeof saved.pairingToken==="string")tokenField.value=saved.pairingToken;
}).catch(()=>{});
tokenField.addEventListener("change",()=>{
  sessionStore?.set({pairingToken:tokenField.value.trim()}).catch(()=>{});
});
executeField.addEventListener("change",()=>{
  start.textContent=executeField.checked?"Start automatic play":"Capture one frame";
});
start.textContent="Capture one frame";
document.getElementById("start").addEventListener("click",async()=>{
  starting=true;start.disabled=true;status.textContent="Checking local bridge…";
  try{
    const token=tokenField.value.trim();
    if(sessionStore)await sessionStore.set({pairingToken:token});
    const result=await chrome.runtime.sendMessage({type:"start",token,execute:executeField.checked});
    status.textContent=result.status || result.error;
  }catch(error){status.textContent=error.message;}
  finally{starting=false;start.disabled=false;}
});
document.getElementById("stop").addEventListener("click",async()=>{
  const result=await chrome.runtime.sendMessage({type:"stop"});status.textContent=result.status;
});
chrome.runtime.sendMessage({type:"status"}).then(result=>{status.textContent=result.status;});
setInterval(()=>{
  if(!starting)chrome.runtime.sendMessage({type:"status"}).then(result=>{status.textContent=result.status;}).catch(()=>{});
},500);
