/* Pranks: things players throw at each other for fun. They fly from the thrower's seat to the target's,
   land with a sound and leave a short mark on the target's picture. They never change the game.
   The server says what you may throw (room.prankKinds) and sends recent throws (room.pranks).
   Usage: Pranks.mount({act, seat: pid => element or null}); Pranks.update(room, me, {hide}) after every
   update. Without a seat function, a thrown thing lands on the first visible [data-pid] element.
   In Werewolf, tapping a seat that isn't part of a game move opens the tray aimed at that player.
   Sounds are files in /sounds named after each prank (fart.mp3, kiss.wav...), plus whoosh for the throw. */
(function(){
  const KINDS = {
    fart:        {e:"💨", name:"Fart",          verb:"farted on"},
    firecracker: {e:"🧨", name:"Firecracker",   verb:"lit a firecracker under"},
    balloon:     {e:"💦", name:"Water balloon", verb:"soaked"},
    curse:       {e:"📜", name:"Curse charm",   verb:"cursed"},
    goldfish:    {e:"🐟", name:"Goldfish",      verb:"slapped a goldfish on"},
    takoyaki:    {e:"🐙", name:"Takoyaki",      verb:"pelted takoyaki at"},
    kiss:        {e:"💋", name:"Kiss",          verb:"kissed"},
    fahhh:       {e:"😩", name:"Fahhh",         verb:"went FAHHH at"},
    hearts:      {e:"💗", name:"Lantern hearts",verb:"sent hearts to"},
    crown:       {e:"👑", name:"Flower crown",  verb:"crowned"},
    boo:         {e:"👻", name:"Boo",           verb:"haunted"},
    chill:       {e:"❄️", name:"Chill",         verb:"froze"},
  };
  const css = `
  .pk-fab{position:fixed;left:max(14px,env(safe-area-inset-left,0px));bottom:calc(var(--chat-lift,0px) + 16px + env(safe-area-inset-bottom,0px));z-index:35;width:56px;height:56px;border-radius:50%;border:2px solid var(--night,#1B1F4B);background:var(--gold,#D9A441);color:var(--ink,#1E1A2E);display:grid;place-items:center;cursor:pointer;font-size:26px;box-shadow:0 10px 26px -8px rgba(0,0,0,.7);transition:transform .15s}
  .pk-fab:active{transform:scale(.92)}
  .pk-fab.cool{background:conic-gradient(var(--gold,#D9A441) calc(var(--p,1) * 360deg),color-mix(in srgb,var(--gold,#D9A441) 35%,var(--night,#1B1F4B)) 0)}
  .pk-fab.cool span{opacity:.5}
  .pk-fab b{position:absolute;inset:0;display:grid;place-items:center;font:900 16px var(--body,system-ui);color:var(--ink,#1E1A2E)}
  .pk-scrim{position:fixed;inset:0;z-index:60;background:rgba(8,9,24,.55);display:grid;align-items:end;justify-items:center;animation:pkfade .2s}
  @media (min-width:760px){.pk-scrim{align-items:center}}
  @keyframes pkfade{from{opacity:0}}
  .pk-sheet{width:min(520px,100%);max-height:86vh;overflow:auto;background:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E);border-radius:18px 18px 0 0;padding:16px 16px calc(16px + env(safe-area-inset-bottom,0px));font-family:var(--body,system-ui);animation:pkup .28s cubic-bezier(.2,.9,.3,1)}
  @media (min-width:760px){.pk-sheet{border-radius:18px}}
  @keyframes pkup{from{transform:translateY(60px);opacity:0}}
  .pk-head{display:flex;align-items:center;gap:10px;margin-bottom:12px}
  .pk-head h2{font:400 24px/1.1 var(--display,serif);margin:0;flex:1}
  .pk-head button{border:0;background:rgba(30,26,46,.08);color:inherit;border-radius:999px;height:38px;min-width:38px;padding:0 12px;font:700 14px var(--body,system-ui);cursor:pointer}
  .pk-items{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}
  @media (max-width:420px){.pk-items{grid-template-columns:repeat(4,1fr)}}
  .pk-items button{border:2px solid transparent;background:#fff;border-radius:14px;padding:10px 4px 8px;display:grid;justify-items:center;gap:2px;cursor:pointer;font:700 13px/1.2 var(--body,system-ui);color:inherit}
  .pk-items button span{font-size:30px;line-height:1.1}
  .pk-items button.on{border-color:var(--lantern,#F2603A)}
  .pk-items button:disabled,.pk-people button:disabled{opacity:.45;cursor:not-allowed}
  .pk-wait{font:700 14px var(--body,system-ui);color:var(--ink-2,#5B5670);margin:-4px 0 10px}
  .pk-sheet h3{font:700 15px var(--body,system-ui);margin:16px 0 8px;color:var(--ink-2,#5B5670)}
  .pk-people{display:grid;grid-template-columns:repeat(auto-fill,minmax(72px,1fr));gap:10px}
  .pk-people button{border:0;background:none;padding:0;display:grid;justify-items:center;gap:4px;cursor:pointer;font:700 13px var(--body,system-ui);color:inherit;min-width:0}
  .pk-people .pic{width:56px;height:56px;border-radius:50%;overflow:hidden;display:grid;place-items:center;background:var(--gold,#D9A441);font-weight:900;font-size:20px;box-shadow:0 0 0 0 var(--lantern,#F2603A);transition:box-shadow .15s}
  .pk-people .pic img{width:100%;height:100%;object-fit:cover;object-position:top}
  .pk-people button:hover .pic,.pk-people button:focus-visible .pic{box-shadow:0 0 0 3px var(--lantern,#F2603A)}
  .pk-people b{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .pk-err{color:#B3261E;font-size:14px;min-height:1.3em;margin-top:8px}
  .pk-fly{position:fixed;left:0;top:0;z-index:70;pointer-events:none;font-size:38px;line-height:1;will-change:transform}
  .pk-fx{position:fixed;left:0;top:0;z-index:69;pointer-events:none;font-size:24px;line-height:1;will-change:transform,opacity}
  .pk-mark{position:fixed;z-index:68;pointer-events:none;border-radius:50%;display:grid;place-items:center}
  .pk-feed{position:fixed;left:50%;top:calc(70px + env(safe-area-inset-top,0px));transform:translateX(-50%);z-index:66;display:grid;gap:6px;justify-items:center;pointer-events:none;width:min(92vw,420px)}
  .pk-feed div{background:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E);border-radius:999px;padding:6px 14px;font:700 14px/1.3 var(--body,system-ui);box-shadow:0 8px 20px -8px rgba(0,0,0,.6);animation:pkfeed 3.4s forwards;text-align:center}
  @keyframes pkfeed{0%{opacity:0;transform:translateY(-8px)}10%,80%{opacity:1;transform:none}100%{opacity:0}}
  .pk-back{position:fixed;left:50%;bottom:calc(var(--chat-lift,0px) + 86px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);z-index:66;border:0;border-radius:999px;padding:11px 18px;background:var(--lantern,#F2603A);color:var(--on-lantern,#1E1A2E);font:900 15px var(--body,system-ui);cursor:pointer;box-shadow:0 12px 30px -8px rgba(0,0,0,.8);animation:pkpop .35s cubic-bezier(.3,1.6,.5,1)}
  .pk-back i{position:absolute;left:14px;right:14px;bottom:4px;height:3px;border-radius:2px;background:rgba(30,26,46,.35);transform-origin:left;animation:pkdrain 5s linear forwards}
  @keyframes pkpop{from{transform:translateX(-50%) scale(.4);opacity:0}}
  @keyframes pkdrain{to{transform:scaleX(0)}}
  .pk-shake{animation:pkshake .5s}
  @keyframes pkshake{20%{translate:-5px 2px}40%{translate:5px -2px}60%{translate:-3px 1px}80%{translate:3px 0}}`;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const calm = () => matchMedia("(prefers-reduced-motion:reduce)").matches;

  let act = null, seatOf = pid => anyFace(pid), room = null, me = null, seen = null, close = null, backBtn = null;
  const fab = document.createElement("button");
  fab.className = "pk-fab"; fab.type = "button"; fab.hidden = true; fab.title = "Prank someone"; fab.setAttribute("aria-label", "Prank someone");
  fab.innerHTML = '<span>🧨</span><b hidden></b>';
  const feed = document.createElement("div"); feed.className = "pk-feed"; feed.setAttribute("aria-live", "polite");

  /* ---------- sound: effects from /sounds, played through Web Audio ---------- */
  let sound = (()=>{ try{ return localStorage.getItem("gn:prankSound") !== "off"; }catch(e){ return true; } })(), ctx = null;
  const buffers = {}, VOL = {whoosh:.35};
  function audio(){
    if(!ctx){ try{ ctx = new (window.AudioContext || window.webkitAudioContext)(); }catch(e){ return null; } }
    if(ctx.state === "suspended") ctx.resume().catch(()=>{});
    return ctx;
  }
  // phones only allow sound after the first tap on the page
  ["pointerdown", "keydown"].forEach(ev => document.addEventListener(ev, () => audio(), {once:true, capture:true}));
  function load(name){
    if(!buffers[name]) buffers[name] = fetch(`/sounds/${name}`).then(r => r.arrayBuffer()).then(b => audio().decodeAudioData(b)).catch(() => null);
    return buffers[name];
  }
  async function playSound(name){
    if(!sound) return;
    const c = audio(); if(!c) return;
    const buf = await load(name); if(!buf) return;
    const src = c.createBufferSource(), g = c.createGain();
    src.buffer = buf; g.gain.value = VOL[name] ?? 1;
    src.connect(g); g.connect(c.destination); src.start();
  }
  const SOUND = new Proxy({}, {get: (_, name) => () => playSound(name)});

  /* ---------- where things are on screen ---------- */
  function center(el){ const r = el.getBoundingClientRect(); return {x: r.left + r.width/2, y: r.top + r.height/2, w: r.width}; }
  const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; };
  const anyFace = pid => [...document.querySelectorAll(`[data-pid="${CSS.escape(pid)}"]`)].find(visible) || null;
  function fromPoint(pid){ const el = seatOf(pid); if(el) return center(el); return {x: window.innerWidth/2, y: window.innerHeight + 40, w: 60}; }
  function toPoint(pid){ const el = seatOf(pid); if(el) return center(el); return {x: window.innerWidth/2, y: window.innerHeight*.35, w: 80}; }
  function spawn(cls, text, x, y, size){
    const s = document.createElement("span"); s.className = cls; s.textContent = text;
    if(size) s.style.fontSize = size + "px";
    s.style.transform = `translate(${x}px,${y}px) translate(-50%,-50%)`;
    document.body.appendChild(s); return s;
  }
  // particles that burst out of a point and fade
  function burst(p, chars, n, spread, dur, up=0){
    for(let i = 0; i < n; i++){
      const a = Math.random()*Math.PI*2, d = spread*(.4 + Math.random()*.6), s = spawn("pk-fx", chars[i % chars.length], p.x, p.y, 16 + Math.random()*14);
      s.animate([{transform:`translate(${p.x}px,${p.y}px) translate(-50%,-50%) scale(.4)`, opacity:1},
                 {transform:`translate(${p.x + Math.cos(a)*d}px,${p.y + Math.sin(a)*d - up}px) translate(-50%,-50%) scale(1)`, opacity:0}],
                {duration: dur*(.7 + Math.random()*.5), easing:"cubic-bezier(.1,.8,.3,1)"}).onfinish = ()=>s.remove();
    }
  }
  // a mark that stays on the target's picture for a while and follows it if the table redraws
  function mark(pid, html, ms, cls=""){
    const m = document.createElement("div"); m.className = "pk-mark " + cls; m.innerHTML = html; document.body.appendChild(m);
    const end = performance.now() + ms;
    (function follow(){
      const el = seatOf(pid);
      if(!el || performance.now() > end){ m.animate([{opacity:1},{opacity:0}], {duration:400}).onfinish = ()=>m.remove(); return; }
      const r = el.getBoundingClientRect();
      Object.assign(m.style, {left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px"});
      requestAnimationFrame(follow);
    })();
  }
  function shake(pid){ const el = seatOf(pid); if(!el || calm()) return; el.classList.remove("pk-shake"); void el.offsetWidth; el.classList.add("pk-shake"); setTimeout(()=>el.classList.remove("pk-shake"), 600); }

  const IMPACT = {
    fart(p, pid){ burst(p, ["💨","☁️"], 9, p.w*.9, 1400, 10); mark(pid, '<span style="font-size:22px;position:absolute;right:-10px;top:-10px">🤢</span>', 4000); },
    firecracker(p, pid){ burst(p, ["✨","💥","🔸"], 14, p.w*1.2, 800); shake(pid);
      mark(pid, '', 6000, "pk-soot"); },
    balloon(p, pid){ burst(p, ["💧","💦"], 12, p.w, 900); mark(pid, '<span style="position:absolute;inset:0;border-radius:50%;background:linear-gradient(180deg,rgba(90,170,255,.55),rgba(90,170,255,.15));"></span><span style="position:absolute;bottom:-14px;left:40%;font-size:16px">💧</span>', 5000); },
    curse(p, pid){ mark(pid, '<span style="position:absolute;left:50%;top:-6%;transform:translateX(-50%) rotate(-6deg);width:34%;height:96%;background:#F7EED7;border:2px solid #B3261E;border-radius:3px;box-shadow:0 4px 10px rgba(0,0,0,.4);display:grid;place-items:center;color:#B3261E;font:900 14px/1 serif;writing-mode:vertical-rl">呪</span>', 8000);
      burst(p, ["💜","✴️"], 6, p.w*.8, 1200); },
    goldfish(p, pid){ shake(pid); burst(p, ["💧"], 6, p.w*.7, 700); mark(pid, '<span style="position:absolute;left:50%;top:-30%;transform:translateX(-50%);font-size:26px;animation:pkbob 1s ease-in-out infinite">🐟</span>', 6000); },
    takoyaki(p, pid){ burst(p, ["🟤","🟫","🐙"], 10, p.w*.8, 900); mark(pid, '<span style="position:absolute;inset:18%;border-radius:50%;background:radial-gradient(circle at 30% 40%,#5a2e12 0 12%,transparent 13%),radial-gradient(circle at 65% 60%,#5a2e12 0 9%,transparent 10%),radial-gradient(circle at 50% 25%,#7a3e18 0 7%,transparent 8%)"></span>', 5000); },
    hearts(p){ burst(p, ["💗","💖","🏮"], 12, p.w, 1600, 60); },
    kiss(p, pid){ burst(p, ["💕","💗"], 6, p.w*.8, 1300, 40);
      mark(pid, '<span style="position:absolute;right:-6%;top:42%;font-size:22px;transform:rotate(-18deg)">💋</span>', 8000); },
    fahhh(p, pid){ shake(pid);
      mark(pid, '<span style="position:absolute;left:50%;bottom:104%;transform:translateX(-50%);white-space:nowrap;background:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E);border-radius:14px;padding:4px 12px;font:400 22px/1.1 var(--display,serif);box-shadow:0 6px 16px rgba(0,0,0,.5);animation:pkfah .5s cubic-bezier(.3,1.7,.5,1)">FAHHH</span>', 2600); },
    crown(p, pid){ burst(p, ["🌸","✨"], 8, p.w*.9, 1200); mark(pid, '<span style="position:absolute;left:50%;top:-34%;transform:translateX(-50%);font-size:30px">👑</span>', 8000); },
    boo(p, pid){ burst(p, ["👻","🕯️"], 5, p.w, 1600, 40); mark(pid, '<span style="position:absolute;inset:0;border-radius:50%;backdrop-filter:grayscale(1) blur(1px);background:rgba(200,200,255,.15)"></span>', 4000); },
    chill(p, pid){ burst(p, ["❄️","✳️"], 10, p.w, 1300); mark(pid, '<span style="position:absolute;inset:-6%;border-radius:50%;box-shadow:inset 0 0 0 4px rgba(190,230,255,.9),0 0 18px rgba(190,230,255,.8);background:rgba(190,230,255,.2)"></span>', 6000); },
  };
  style.textContent += `@keyframes pkfah{from{transform:translateX(-50%) scale(.3)}} @keyframes pkbob{50%{translate:0 -5px;rotate:12deg}} .pk-soot::after{content:"";position:absolute;inset:8%;border-radius:50%;background:radial-gradient(circle at 40% 45%,rgba(20,15,10,.75) 0 18%,transparent 40%),radial-gradient(circle at 65% 60%,rgba(20,15,10,.6) 0 12%,transparent 30%)}`;

  function play(x){
    const k = KINDS[x.kind]; if(!k) return;
    const a = fromPoint(x.from), b = toPoint(x.to);
    const thrower = (room.players[x.from] || {}).name || "Someone", target = (room.players[x.to] || {}).name || "someone";
    const line = document.createElement("div");
    line.textContent = x.to === me?.pid ? `${thrower} ${k.verb} you` : x.from === me?.pid ? `You ${k.verb} ${target}` : `${thrower} ${k.verb} ${target}`;
    feed.appendChild(line); setTimeout(()=>line.remove(), 3500);
    const land = ()=>{ (SOUND[x.kind] || (()=>{}))(); IMPACT[x.kind] && IMPACT[x.kind](toPoint(x.to), x.to); };
    if(calm()){ land(); return; }
    SOUND.whoosh();
    const f = spawn("pk-fly", k.e, a.x, a.y);
    const midX = (a.x + b.x)/2, midY = Math.min(a.y, b.y) - 90 - Math.abs(a.x - b.x)*.15;
    f.animate([
      {transform:`translate(${a.x}px,${a.y}px) translate(-50%,-50%) scale(.6) rotate(0deg)`},
      {transform:`translate(${midX}px,${midY}px) translate(-50%,-50%) scale(1.25) rotate(200deg)`, offset:.5},
      {transform:`translate(${b.x}px,${b.y}px) translate(-50%,-50%) scale(.9) rotate(400deg)`},
    ], {duration:720, easing:"cubic-bezier(.35,.1,.6,1)"}).onfinish = ()=>{ f.remove(); land(); };
  }

  /* ---------- throw it back ---------- */
  function offerBack(x){
    if(backBtn) backBtn.remove();
    const name = (room.players[x.from] || {}).name || "them";
    backBtn = document.createElement("button"); backBtn.className = "pk-back"; backBtn.type = "button";
    backBtn.innerHTML = `Throw it back at ${esc(name)}<i></i>`;
    document.body.appendChild(backBtn);
    const b = backBtn, t = setTimeout(()=>{ b.remove(); if(backBtn === b) backBtn = null; }, 5000);
    b.onclick = async ()=>{
      clearTimeout(t); b.remove(); backBtn = null;
      const kinds = room.prankKinds || [], kind = kinds.includes(x.kind) ? x.kind : kinds[0];
      if(kind) send(kind, x.from, true);
    };
  }

  // cooldown: the server says how long until you can throw again; the button fills back up meanwhile
  let readyAt = 0, coolTotal = 6;
  const waitLeft = () => Math.max(0, readyAt - Date.now()) / 1000;
  function tickCool(){
    const left = waitLeft();
    fab.classList.toggle("cool", left > 0);
    fab.style.setProperty("--p", 1 - left / coolTotal);
    const b = fab.querySelector("b"); b.hidden = !(left > 0); b.textContent = Math.ceil(left);
    fab.setAttribute("aria-label", left > 0 ? `Prank someone (ready in ${Math.ceil(left)} seconds)` : "Prank someone");
    const w = document.querySelector(".pk-wait");
    if(w){ w.hidden = !(left > 0); w.textContent = `Reloading. Ready in ${Math.ceil(left)}s.`; document.querySelectorAll(".pk-items button, .pk-people button").forEach(x => x.disabled = left > 0); }
    if(left > 0) requestAnimationFrame(tickCool);
  }
  function startCool(sec){ readyAt = Date.now() + sec * 1000; tickCool(); }
  async function send(kind, to, back=false){
    if(waitLeft() > 0) return `Reloading. Ready in ${Math.ceil(waitLeft())}s.`;
    try{ await act("prank", {kind, to, back}); startCool(coolTotal); return null; }
    catch(err){ return err.message; }
  }

  /* ---------- the tray ---------- */
  function open(target){
    if(close || !room || !(room.prankKinds || []).length) return;
    const kinds = room.prankKinds;
    let pick = kinds[0];
    const scrim = document.createElement("div"); scrim.className = "pk-scrim";
    const people = Object.entries(room.players).filter(([pid]) => pid !== me.pid);
    const pic = p => { const src = window.Avatars ? Avatars.src(p) : null; return src ? `<img src="${esc(src)}" alt="">` : esc((p.name || "?")[0].toUpperCase()); };
    const draw = () => {
      const t = target && room.players[target];
      scrim.innerHTML = `<div class="pk-sheet" role="dialog" aria-label="Prank someone"><div class="pk-head"><h2>${t ? `Prank ${esc(t.name)}` : "Prank someone"}</h2>
        <button type="button" data-sound aria-pressed="${sound}">${sound ? "Sound on" : "Sound off"}</button><button type="button" data-close aria-label="Close">×</button></div>
        <div class="pk-wait" hidden></div><div class="pk-items">${kinds.map(k => `<button type="button" data-kind="${k}" class="${!t && k === pick ? "on" : ""}"><span>${KINDS[k].e}</span>${KINDS[k].name}</button>`).join("")}</div>
        ${t ? "" : `<h3>Then tap who gets it</h3><div class="pk-people">${people.map(([pid, p]) => `<button type="button" data-to="${pid}"><span class="pic">${pic(p)}</span><b>${esc(p.name)}</b></button>`).join("")}</div>`}
        <div class="pk-err" role="alert"></div></div>`;
    };
    draw();
    document.body.appendChild(scrim);
    tickCool();
    close = () => { scrim.remove(); close = null; };
    const fire = async (kind, to) => {
      const err = await send(kind, to);
      if(err){ scrim.querySelector(".pk-err").textContent = err; return; }
      close();
    };
    scrim.onclick = e => {
      if(e.target === scrim || e.target.closest("[data-close]")){ close(); return; }
      if(e.target.closest("[data-sound]")){ sound = !sound; try{ localStorage.setItem("gn:prankSound", sound ? "on" : "off"); }catch(err){} draw(); tickCool(); return; }
      const k = e.target.closest("[data-kind]");
      if(k){ if(target) fire(k.dataset.kind, target); else { pick = k.dataset.kind; draw(); } return; }
      const to = e.target.closest("[data-to]");
      if(to) fire(pick, to.dataset.to);
    };
  }

  function mount(opts){
    act = opts.act; seatOf = opts.seat || seatOf;
    document.body.append(fab, feed);
    fab.onclick = () => open(null);
    // tapping someone's seat when it isn't a game move aims the tray at them
    document.addEventListener("click", e => {
      const s = e.target.closest("[data-seat]");
      if(!s || s.classList.contains("pick") || !room || !me || s.dataset.seat === me.pid) return;
      open(s.dataset.seat);
    });
    if(window.BackGuard) BackGuard.onBack(() => { if(!close) return false; close(); return true; });
  }
  function update(r, m, opts={}){
    room = r; me = m;
    const joined = !!(me && room && room.players && room.players[me.pid]);
    fab.hidden = !joined || !(room.prankKinds || []).length || !!opts.hide || Object.keys(room.players).length < 2;
    if(room.prankCooldown) coolTotal = room.prankCooldown;
    if(room.prankWait > 0 && Math.abs(Date.now() + room.prankWait * 1000 - readyAt) > 1500) startCool(room.prankWait);
    const list = (room && room.pranks) || [];
    if(seen === null){ seen = new Set(list.map(x => x.id)); return; }  // don't replay what happened before you arrived
    for(const x of list){
      if(seen.has(x.id)) continue;
      seen.add(x.id);
      play(x);
      if(joined && x.to === me.pid && !x.back) setTimeout(() => offerBack(x), 800);
    }
  }
  window.Pranks = {mount, update, open, KINDS};
})();
