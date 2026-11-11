const status=document.getElementById("status");
const start=document.getElementById("start");
let starting=false;
document.getElementById("start").addEventListener("click",async()=>{
  starting=true;start.disabled=true;status.textContent="Checking local bridge…";
  try{
    const result=await chrome.runtime.sendMessage({type:"start",token:document.getElementById("token").value.trim(),execute:document.getElementById("execute").checked});
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
