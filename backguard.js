/* The phone's Back button, made game-friendly: inside a room, Back first closes whatever is open
   (the avatar picker, or anything a page registers with BackGuard.onBack), and leaving the game
   takes a second press within 2.5 seconds. Usage: BackGuard.arm() once you're in a room. */
(function(){
  let armed = false, leaving = false;
  const handlers = [];
  const style = document.createElement("style");
  style.textContent = `.bg-toast{position:fixed;left:50%;bottom:calc(90px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);z-index:200;
    background:#f3eefc;color:#140f24;font:800 14px/1.3 Manrope,system-ui,sans-serif;border-radius:999px;padding:10px 18px;box-shadow:0 10px 30px rgba(0,0,0,.5);white-space:nowrap}`;
  document.head.appendChild(style);

  function toast(msg){
    let t = document.querySelector(".bg-toast");
    if(!t){ t = document.createElement("div"); t.className = "bg-toast"; document.body.appendChild(t); }
    t.textContent = msg; t.hidden = false;
    clearTimeout(toast.timer); toast.timer = setTimeout(()=>{ t.hidden = true; }, 2400);
  }
  function arm(){
    armed = true;
    if(!history.state || !history.state.guard) history.pushState({guard:1}, "");
  }
  window.addEventListener("popstate", ()=>{
    if(!armed) return;
    // something open on screen? Back closes it and you stay put
    const picker = document.querySelector(".av-scrim .av-x");
    if(picker){ picker.click(); history.pushState({guard:1}, ""); return; }
    for(const h of handlers){ if(h()){ history.pushState({guard:1}, ""); return; } }
    if(leaving){ history.back(); return; }  // second press: really leave
    leaving = true;
    toast("Press back again to leave the game");
    history.pushState({guard:1}, "");
    setTimeout(()=>{ leaving = false; }, 2500);
  });
  window.BackGuard = {arm, onBack: h => handlers.push(h)};
})();
