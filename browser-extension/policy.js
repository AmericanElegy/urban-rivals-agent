export function allowedURL(value){
  try{const u=new URL(value);return u.origin==="https://www.urban-rivals.com"&&u.pathname==="/game/play/webgl/"&&!u.search;}
  catch{return false;}
}
export function validateAction(result,frame){
  if(result.sequence!==frame.sequence||result.run_id!==frame.run_id)throw new Error("Mismatched action receipt");
  if(!result.action)return null;
  if(Date.now()/1000-frame.captured_at>20)throw new Error("Stale action");
  const a=result.action;
  if(a.type!=="click"||!Number.isFinite(a.x)||!Number.isFinite(a.y)||a.x<0||a.x>1||a.y<0||a.y>1)throw new Error("Invalid canvas action");
  return a;
}
export function validateTarget(tab,window,execute){
  if(!allowedURL(tab.url))throw new Error("Game tab navigated away; stopped");
  if(!tab.active)throw new Error("Another tab is selected in the game window; stopped");
  if(execute&&!window.focused)throw new Error("Game window lost focus; live input stopped");
  return tab;
}
