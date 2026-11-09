/* Shared avatar picker for every game: pick an anime character, or upload a picture from your
   gallery. Usage: Avatars.open(act) where act(action, body) posts to the room; Avatars.src(player)
   gives the picture URL (or null). */
(function(){
  const css = `
  .av-scrim{position:fixed;left:0;right:0;top:var(--vv-top,0px);height:var(--vv-h,100dvh);z-index:100;background:rgba(8,9,24,.7);display:grid;place-items:stretch;animation:avfade .2s}
  @media (min-width:700px){.av-scrim{place-items:center}}
  @keyframes avfade{from{opacity:0}}
  .av-sheet{width:100%;height:100%;min-height:0;display:grid;grid-template-rows:auto auto auto 1fr;background:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E);font-family:var(--body,system-ui);animation:avup .3s cubic-bezier(.2,.9,.3,1);padding-top:env(safe-area-inset-top,0px)}
  @media (min-width:700px){.av-sheet{width:min(720px,100%);height:auto;max-height:88vh;border-radius:18px;box-shadow:0 30px 80px rgba(0,0,0,.6);padding-top:0}}
  @keyframes avup{from{transform:translateY(40px);opacity:0}}
  .av-head{display:flex;align-items:center;gap:10px;padding:18px 18px 10px}
  .av-head h2{margin:0;font:400 26px/1.1 var(--display,serif);flex:1}
  .av-x{border:0;background:rgba(30,26,46,.08);color:inherit;border-radius:999px;width:40px;height:40px;font-size:20px;cursor:pointer}
  .av-tools{display:flex;gap:8px;padding:0 18px 12px;flex-wrap:wrap}
  .av-tools input{flex:1;min-width:150px;background:#fff;border:1px solid rgba(30,26,46,.2);border-radius:999px;padding:10px 16px;color:inherit;font:inherit;font-size:16px;outline:none}
  .av-tools input:focus{border-color:var(--lantern,#F2603A)}
  .av-up{border:0;border-radius:999px;padding:10px 16px;font:inherit;font-weight:700;background:var(--ink,#1E1A2E);color:var(--paper,#F3EBDD);cursor:pointer}
  .av-chips{display:flex;gap:6px;padding:0 18px 12px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
  .av-chips button{flex:none;border:1px solid rgba(30,26,46,.25);background:none;color:inherit;border-radius:999px;padding:6px 13px;font:inherit;font-size:14px;font-weight:700;cursor:pointer}
  .av-chips button.on{background:var(--ink,#1E1A2E);color:var(--paper,#F3EBDD);border-color:var(--ink,#1E1A2E)}
  .av-grid{overflow:auto;min-height:0;overscroll-behavior:contain;padding:4px 18px calc(18px + env(safe-area-inset-bottom,0px));display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:12px;align-content:start}
  .av-tile{border:0;background:none;padding:0;cursor:pointer;color:inherit;font:inherit;display:grid;gap:4px;text-align:center}
  .av-tile img{width:100%;aspect-ratio:1;object-fit:cover;object-position:top;border-radius:50%;background:var(--night,#1B1F4B);display:block;box-shadow:0 0 0 0 var(--lantern,#F2603A);transition:box-shadow .15s,transform .15s}
  .av-tile:hover img,.av-tile:focus-visible img{box-shadow:0 0 0 3px var(--lantern,#F2603A);transform:translateY(-2px)}
  .av-tile b{font-size:14px;line-height:1.2}
  .av-tile small{font-size:12px;color:var(--ink-2,#5B5670);line-height:1.2}
  .av-msg{grid-column:1/-1;color:var(--ink-2,#5B5670);text-align:center;padding:20px}`;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);
  const file = document.createElement("input"); file.type = "file"; file.accept = "image/*"; file.hidden = true; document.body.appendChild(file);
  let list = null, act = null, close = null, show = "";
  // one filter per show in the list, the shows with the most characters first
  function shows(){
    const n = {};
    (list||[]).forEach(c=>{ if(c.show) n[c.show] = (n[c.show]||0) + 1; });
    return [["", "All"], ...Object.keys(n).sort((a,b)=>n[b]-n[a] || a.localeCompare(b)).map(s=>[s, `${s} · ${n[s]}`])];
  }
  function chips(){
    const el = document.querySelector(".av-chips"); if(!el) return;
    el.innerHTML = shows().map(([v,t])=>`<button data-show="${esc(v)}" class="${v===show?"on":""}">${esc(t)}</button>`).join("");
  }
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  async function load(){
    if(list) return list;
    try{ const r = await fetch("/api/avatars"); list = (await r.json()).avatars || []; }catch(e){ list = []; }
    return list;
  }
  load();  // warm the list so the picker opens instantly

  function grid(q){
    const g = document.querySelector(".av-grid"); if(!g) return;
    const ql = q.trim().toLowerCase();
    const items = (list||[]).filter(c=>(!show || c.show === show) && (!ql || c.name.toLowerCase().includes(ql) || c.show.toLowerCase().includes(ql) || (c.alias||"").toLowerCase().includes(ql)));
    g.scrollTop = 0;  // new results start at the top, right under the search box
    g.innerHTML = list === null ? '<div class="av-msg">Loading characters…</div>'
      : items.length ? items.map(c=>`<button class="av-tile" data-url="${esc(c.img)}" title="${esc(c.name)} · ${esc(c.show)}"><img src="${esc(c.img)}" alt="" loading="lazy" referrerpolicy="no-referrer"><b>${esc(c.name)}</b><small>${esc(c.show)}</small></button>`).join("")
      : `<div class="av-msg">${list.length ? "No character matches that." : "Characters couldn't load right now. Upload a picture instead."}</div>`;
  }

  async function open(actFn){
    act = actFn;
    const scrim = document.createElement("div"); scrim.className = "av-scrim";
    scrim.innerHTML = `<div class="av-sheet" role="dialog" aria-label="Pick your picture"><div class="av-head"><h2>Pick your picture</h2><button class="av-x" aria-label="Close">×</button></div>
      <div class="av-tools"><input type="text" placeholder="Search a character or show" aria-label="Search characters"><button class="av-up">Upload a photo</button></div>
      <div class="av-chips"></div><div class="av-grid"></div></div>`;
    document.body.appendChild(scrim);
    // the visible area shrinks when the phone keyboard opens: size the picker to it
    const vv = window.visualViewport;
    const fit = ()=>{ if(!vv) return; scrim.style.setProperty("--vv-h", vv.height + "px"); scrim.style.setProperty("--vv-top", vv.offsetTop + "px"); };
    fit(); vv && vv.addEventListener("resize", fit); vv && vv.addEventListener("scroll", fit);
    close = ()=>{ vv && vv.removeEventListener("resize", fit); vv && vv.removeEventListener("scroll", fit); scrim.remove(); close = null; };
    scrim.onclick = e=>{ if(e.target === scrim || e.target.closest(".av-x")) close(); };
    scrim.querySelector(".av-up").onclick = ()=>file.click();
    const search = scrim.querySelector("input");
    search.oninput = ()=>grid(search.value);
    search.onkeydown = e=>{ if(e.key === "Enter"){ e.preventDefault(); search.blur(); } };  // the keyboard's search key closes it and shows results
    search.setAttribute("enterkeyhint", "search");
    scrim.querySelector(".av-chips").onclick = e=>{ const b = e.target.closest("[data-show]"); if(!b) return;
      show = b.dataset.show; scrim.querySelectorAll(".av-chips button").forEach(x=>x.classList.toggle("on", x===b)); grid(search.value); };
    scrim.querySelector(".av-grid").onclick = async e=>{
      const t = e.target.closest(".av-tile"); if(!t) return;
      search.blur();
      try{ await act("avatar", {url: t.dataset.url}); remember({url: t.dataset.url}); close && close(); }catch(err){ alertish(err.message); }
    };
    chips(); grid(""); await load(); chips(); grid(search.value);
  }

  file.onchange = async ()=>{
    const f = file.files[0]; file.value = ""; if(!f || !act) return;
    try{
      const img = await new Promise((res, rej)=>{ const i = new Image(); i.onload = ()=>res(i); i.onerror = ()=>rej(new Error("That file isn't a picture we can read.")); i.src = URL.createObjectURL(f); });
      const c = document.createElement("canvas"); c.width = c.height = 320; const x = c.getContext("2d");
      const m = Math.min(img.width, img.height); x.drawImage(img, (img.width-m)/2, (img.height-m)/2, m, m, 0, 0, 320, 320);
      const data = c.toDataURL("image/jpeg", .85);
      await act("photo", {img: data});
      remember({img: data});
      close && close();
    }catch(err){ alertish(err.message || "That picture didn't work. Try another one."); }
  };

  function alertish(msg){
    const m = document.querySelector(".av-grid"); if(m) m.insertAdjacentHTML("afterbegin", `<div class="av-msg" style="color:#B3261E">${esc(msg)}</div>`);
  }

  /* your profile picture, saved on this device: whatever you pick last follows you into every game */
  const KEY = "gn:avatar", applied = new Set();
  function remember(v){ try{ localStorage.setItem(KEY, JSON.stringify(v)); }catch(e){} }
  function saved(){ try{ const v = JSON.parse(localStorage.getItem(KEY)); return v && v.url && v.url.startsWith("/img/") ? null : v; }catch(e){ return null; } }
  function apply(actFn, player){
    // a player with no picture in this room yet gets their saved one, once per room
    if(!player || player.photo || (player.avatar && !player.avatarAuto)) return;  // a random stand-in face gives way to your own
    const s = saved(), k = location.pathname + location.search + player.name;
    if(!s || applied.has(k)) return;
    applied.add(k);
    (s.url ? actFn("avatar", {url: s.url}) : actFn("photo", {img: s.img})).catch(()=>{});
  }

  window.Avatars = {
    open, apply,
    mine: ()=>{ const s = saved(); return s ? s.url || s.img : null; },
    src: p => p && (p.photo ? `/api/img/${p.photo}` : p.avatar || null),
  };
})();
