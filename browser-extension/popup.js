const status=document.getElementById("status");
document.getElementById("start").addEventListener("click",async()=>{
  try{
    const result=await chrome.runtime.sendMessage({type:"start",token:document.getElementById("token").value.trim(),execute:document.getElementById("execute").checked});
    status.textContent=result.status || result.error;
  }catch(error){status.textContent=error.message;}
});
document.getElementById("stop").addEventListener("click",async()=>{
  const result=await chrome.runtime.sendMessage({type:"stop"});status.textContent=result.status;
});
chrome.runtime.sendMessage({type:"status"}).then(result=>{status.textContent=result.status;});
