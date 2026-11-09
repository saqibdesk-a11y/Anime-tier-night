/* Festival recolors, picked by each player and saved on their device. Every page builds its colors
   from the tokens in festival.css (--night, --night-2, --night-3, --lantern, --gold, --shrine), so a
   theme only swaps those tokens. Usage: load this script; it adds a theme button to the page header
   (inside [data-theme-slot] if the page has one). Theme.onChange(f) runs f after a switch. */
(function(){
  const THEMES = {
    lantern:   {name:"Lantern night", note:"Indigo sky, orange lanterns", night:"#1B1F4B", night2:"#252A5E", night3:"#313773", lantern:"#F2603A", gold:"#D9A441", shrine:"#2E8B6E"},
    fireworks: {name:"Fireworks", note:"Deep navy, pink bursts", night:"#0F1A33", night2:"#182747", night3:"#22355C", lantern:"#EC5B93", gold:"#F2C14E", shrine:"#2B9C9A"},
    snow:      {name:"Snow festival", note:"Slate blue, red torii", night:"#26324A", night2:"#30405C", night3:"#3C4E6E", lantern:"#E0473F", gold:"#D8CFB8", shrine:"#3E8E7E"},
    sakura:    {name:"Sakura evening", note:"Plum dusk, blossom pink", night:"#2A1830", night2:"#38213F", night3:"#472C50", lantern:"#F08CB0", gold:"#E5C06B", shrine:"#4B9A78"},
  };
  const get = (k, d) => { try{ return localStorage.getItem(k) || d; }catch(e){ return d; } };
  const set = (k, v) => { try{ localStorage.setItem(k, v); }catch(e){} };
  let theme = THEMES[get("gn:festival", "lantern")] ? get("gn:festival", "lantern") : "lantern";
  const listeners = [];

  const vars = document.createElement("style");
  vars.id = "gn-theme";
  function apply(){
    const t = THEMES[theme];
    document.documentElement.dataset.festival = theme;
    vars.textContent = `html:root{--night:${t.night};--night-2:${t.night2};--night-3:${t.night3};--lantern:${t.lantern};--gold:${t.gold};--shrine:${t.shrine}}`;
    const meta = document.querySelector('meta[name="theme-color"]'); if(meta) meta.content = t.night;
    listeners.forEach(f => f());
  }

  const css = document.createElement("style");
  css.textContent = `.th-btn{width:40px;height:40px;border-radius:50%;border:1px solid var(--line-2,rgba(243,235,221,.28));background:none;display:inline-grid;place-items:center;padding:0;cursor:pointer;color:inherit;flex:none}
    .th-btn svg{width:20px;height:20px}
    .th-scrim{position:fixed;inset:0;z-index:300;background:rgba(8,9,24,.6);display:grid;align-items:end;justify-items:center;animation:thfade .2s}
    @keyframes thfade{from{opacity:0}}
    .th-sheet{width:min(520px,100%);max-height:86vh;overflow:auto;background:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E);border-radius:18px 18px 0 0;padding:18px 16px calc(18px + env(safe-area-inset-bottom,0px));font:15px/1.5 var(--body,system-ui);animation:thup .3s cubic-bezier(.2,.9,.3,1)}
    @media (min-width:600px){.th-scrim{align-items:center}.th-sheet{border-radius:18px}}
    @keyframes thup{from{transform:translateY(100%)}}
    .th-sheet h2{font:400 26px/1.1 var(--display,serif);margin:0 0 4px}
    .th-sheet p{margin:0 0 14px;color:#5B5670}
    .th-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .th-tile{position:relative;border:3px solid transparent;border-radius:14px;padding:12px 12px 10px;cursor:pointer;text-align:left;color:#F3EBDD;min-height:96px;display:grid;align-content:end;gap:2px;font:inherit}
    .th-tile.on{border-color:var(--ink,#1E1A2E)}
    .th-tile b{font-size:16px}
    .th-tile small{font-size:13px;opacity:.8}
    .th-tile .lamps{position:absolute;top:12px;left:12px;display:flex;gap:6px}
    .th-tile .lamps i{width:14px;height:18px;border-radius:7px}
    .th-close{margin-top:16px;width:100%;border:0;background:var(--ink,#1E1A2E);color:var(--paper,#F3EBDD);border-radius:999px;padding:12px;font:700 15px var(--body,system-ui);cursor:pointer}`;

  let close = null;
  function open(){
    if(close) return;
    const scrim = document.createElement("div"); scrim.className = "th-scrim";
    const draw = () => {
      scrim.innerHTML = `<div class="th-sheet" role="dialog" aria-label="Theme"><h2>Festival colors</h2><p>Only you see this. It applies to every game on this device.</p>
        <div class="th-grid">${Object.entries(THEMES).map(([k, t]) => `<button type="button" class="th-tile ${k === theme ? "on" : ""}" data-th="${k}" style="background:${t.night}" aria-pressed="${k === theme}">
          <span class="lamps"><i style="background:${t.lantern}"></i><i style="background:${t.gold}"></i><i style="background:${t.shrine}"></i></span>
          <b>${t.name}</b><small>${t.note}</small></button>`).join("")}</div>
        <button type="button" class="th-close">Done</button></div>`;
    };
    draw();
    document.body.appendChild(scrim);
    close = () => { scrim.remove(); close = null; };
    scrim.onclick = e => {
      const th = e.target.closest("button[data-th]");
      if(th){ theme = th.dataset.th; set("gn:festival", theme); apply(); draw(); return; }
      if(e.target === scrim || e.target.closest(".th-close")) close();
    };
  }
  if(window.BackGuard) BackGuard.onBack(() => { if(close){ close(); return true; } return false; });

  const ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 3h6M12 3v2"/><path d="M7 7c0-1 2.2-2 5-2s5 1 5 2v8c0 1-2.2 2-5 2s-5-1-5-2z"/><path d="M7 11h10M10 17v2h4v-2"/></svg>`;
  function addButtons(){
    const slots = document.querySelectorAll("[data-theme-slot]");
    (slots.length ? slots : document.querySelectorAll("header.top, .bar .wrap, .hero")).forEach(h => {
      if(h.querySelector(":scope > .th-btn")) return;
      const b = document.createElement("button"); b.className = "th-btn"; b.type = "button"; b.title = "Festival colors"; b.setAttribute("aria-label", "Festival colors"); b.innerHTML = ICON;
      b.onclick = open;
      if(h.classList.contains("hero")){ b.style.cssText = "position:absolute;top:0;right:0"; if(getComputedStyle(h).position === "static") h.style.position = "relative"; }
      const before = h.querySelector(":scope > #soundBtn, :scope > .timer");
      before ? h.insertBefore(b, before) : h.appendChild(b);
    });
  }
  document.head.append(css, vars);
  apply();
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", addButtons); else addButtons();

  window.Theme = {open, cards: () => "classic", onChange: f => listeners.push(f), get: () => theme};
})();
