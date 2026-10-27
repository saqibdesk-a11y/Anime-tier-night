/* Shared avatar picker for every game: pick an anime character, or upload a picture from your
   gallery. Usage: Avatars.open(act) where act(action, body) posts to the room; Avatars.src(player)
   gives the picture URL (or null). */
(function(){
  const css = `
  .av-scrim{position:fixed;inset:0;z-index:100;background:rgba(4,4,10,.72);backdrop-filter:blur(6px);display:grid;place-items:end center;animation:avfade .2s}
  @media (min-width:700px){.av-scrim{place-items:center}}
  @keyframes avfade{from{opacity:0}}
  .av-sheet{width:min(720px,100%);max-height:88vh;display:grid;grid-template-rows:auto auto 1fr;background:#14131d;color:#f1eef8;border:1px solid rgba(255,255,255,.12);border-radius:22px 22px 0 0;box-shadow:0 -20px 60px rgba(0,0,0,.6);font-family:Manrope,system-ui,sans-serif;animation:avup .3s cubic-bezier(.2,.9,.3,1)}
  @media (min-width:700px){.av-sheet{border-radius:22px}}
  @keyframes avup{from{transform:translateY(40px);opacity:0}}
  .av-head{display:flex;align-items:center;gap:10px;padding:16px 18px 10px}
  .av-head h2{margin:0;font-size:19px;flex:1;font-family:inherit;font-weight:800;letter-spacing:0;text-transform:none}
  .av-x{border:0;background:rgba(255,255,255,.08);color:inherit;border-radius:999px;width:36px;height:36px;font-size:18px;cursor:pointer}
  .av-tools{display:flex;gap:8px;padding:0 18px 12px;flex-wrap:wrap}
  .av-tools input{flex:1;min-width:150px;background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:10px 12px;color:inherit;font:inherit;outline:none}
  .av-tools input:focus{border-color:#ffd166}
  .av-up{border:0;border-radius:12px;padding:10px 14px;font:inherit;font-weight:800;background:#ffd166;color:#2a1c00;cursor:pointer}
  .av-grid{overflow:auto;padding:4px 18px calc(18px + env(safe-area-inset-bottom,0px));display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:10px;align-content:start}
  .av-tile{border:2px solid transparent;background:rgba(255,255,255,.05);border-radius:14px;padding:6px;cursor:pointer;color:inherit;font:inherit;display:grid;gap:4px;text-align:center;transition:transform .12s,border-color .15s}
  .av-tile:hover{transform:translateY(-2px);border-color:rgba(255,209,102,.6)}
  .av-tile img{width:100%;aspect-ratio:1;object-fit:cover;object-position:top;border-radius:50%;background:#222;display:block}
  .av-tile b{font-size:11.5px;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .av-tile small{font-size:10px;opacity:.6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .av-msg{grid-column:1/-1;opacity:.7;text-align:center;padding:20px}`;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);
  const file = document.createElement("input"); file.type = "file"; file.accept = "image/*"; file.hidden = true; document.body.appendChild(file);
  let list = null, act = null, close = null;
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
    const items = (list||[]).filter(c=>!ql || c.name.toLowerCase().includes(ql) || c.show.toLowerCase().includes(ql));
    g.innerHTML = list === null ? '<div class="av-msg">Loading characters…</div>'
      : items.length ? items.map(c=>`<button class="av-tile" data-url="${esc(c.img)}" title="${esc(c.name)} · ${esc(c.show)}"><img src="${esc(c.img)}" alt="" loading="lazy" referrerpolicy="no-referrer"><b>${esc(c.name)}</b><small>${esc(c.show)}</small></button>`).join("")
      : `<div class="av-msg">${list.length ? "No character matches that." : "Characters couldn't load right now. Upload a picture instead."}</div>`;
  }

  async function open(actFn){
    act = actFn;
    const scrim = document.createElement("div"); scrim.className = "av-scrim";
    scrim.innerHTML = `<div class="av-sheet" role="dialog" aria-label="Choose your avatar"><div class="av-head"><h2>Choose your avatar</h2><button class="av-x" aria-label="Close">×</button></div>
      <div class="av-tools"><input type="text" placeholder="Search a character or show" aria-label="Search characters"><button class="av-up">Upload from gallery</button></div><div class="av-grid"></div></div>`;
    document.body.appendChild(scrim);
    close = ()=>{ scrim.remove(); close = null; };
    scrim.onclick = e=>{ if(e.target === scrim || e.target.closest(".av-x")) close(); };
    scrim.querySelector(".av-up").onclick = ()=>file.click();
    const search = scrim.querySelector("input");
    search.oninput = ()=>grid(search.value);
    scrim.querySelector(".av-grid").onclick = async e=>{
      const t = e.target.closest(".av-tile"); if(!t) return;
      try{ await act("avatar", {url: t.dataset.url}); close && close(); }catch(err){ alertish(err.message); }
    };
    grid(""); await load(); grid(search.value);
  }

  file.onchange = async ()=>{
    const f = file.files[0]; file.value = ""; if(!f || !act) return;
    try{
      const img = await new Promise((res, rej)=>{ const i = new Image(); i.onload = ()=>res(i); i.onerror = ()=>rej(new Error("That file isn't a picture we can read.")); i.src = URL.createObjectURL(f); });
      const c = document.createElement("canvas"); c.width = c.height = 320; const x = c.getContext("2d");
      const m = Math.min(img.width, img.height); x.drawImage(img, (img.width-m)/2, (img.height-m)/2, m, m, 0, 0, 320, 320);
      await act("photo", {img: c.toDataURL("image/jpeg", .85)});
      close && close();
    }catch(err){ alertish(err.message || "That picture didn't work. Try another one."); }
  };

  function alertish(msg){
    const m = document.querySelector(".av-grid"); if(m) m.insertAdjacentHTML("afterbegin", `<div class="av-msg" style="color:#ff9a9a;opacity:1">${esc(msg)}</div>`);
  }

  window.Avatars = {
    open,
    src: p => p && (p.photo ? `/api/img/${p.photo}` : p.avatar || null),
  };
})();
