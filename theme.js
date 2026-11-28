/* Neon Tokyo Arcade themes, saved per device. Every page builds from the CSS tokens in
   festival.css (--night, --night-2, --night-3, --lantern, --on-lantern, --gold, --shrine),
   so switching themes recolors all 13 games immediately. */
(function(){
  const THEMES = {
    neon:    {name:"Neon Tokyo",      note:"Obsidian glass, electric rose & cyan", night:"#0A0D18", night2:"#12172B", night3:"#1B2340", lantern:"#FF3E78", onLantern:"#FFFFFF", gold:"#FFC83D", shrine:"#00D4AA"},
    cyber:   {name:"Cyber Shibuya",   note:"Midnight void, hyper cyan & violet",   night:"#070B16", night2:"#10172C", night3:"#192342", lantern:"#00E0FF", onLantern:"#06111F", gold:"#C084FC", shrine:"#FF4D9D"},
    sunset:  {name:"Synthwave Dusk",  note:"Deep plum, arcade coral & gold",       night:"#13091F", night2:"#1E1132", night3:"#2B1947", lantern:"#FF6B4A", onLantern:"#FFFFFF", gold:"#FFD166", shrine:"#2EC4B6"},
    emerald: {name:"Akihabara Mint",  note:"Carbon dark, neon emerald & amber",    night:"#081214", night2:"#102024", night3:"#193137", lantern:"#1FE6A8", onLantern:"#051612", gold:"#FFB830", shrine:"#3DA9FC"},
  };
  const get = (k, d) => { try{ return localStorage.getItem(k) || d; }catch(e){ return d; } };
  const set = (k, v) => { try{ localStorage.setItem(k, v); }catch(e){} };
  const saved = get("gn:arcadeTheme", "");
  let theme = THEMES[saved] ? saved : "neon";
  const listeners = [];

  const vars = document.createElement("style");
  vars.id = "gn-theme";
  function apply(){
    const t = THEMES[theme];
    document.documentElement.dataset.festival = theme;
    vars.textContent = `html:root{--night:${t.night};--night-2:${t.night2};--night-3:${t.night3};--lantern:${t.lantern};--on-lantern:${t.onLantern};--gold:${t.gold};--shrine:${t.shrine}}`;
    const meta = document.querySelector('meta[name="theme-color"]'); if(meta) meta.content = t.night;
    listeners.forEach(f => f());
  }

  const css = document.createElement("style");
  css.textContent = `.th-btn{width:38px;height:38px;border-radius:50%;border:1px solid var(--line,rgba(255,255,255,.14));background:rgba(255,255,255,.06);display:inline-grid;place-items:center;padding:0;cursor:pointer;color:inherit;flex:none}
    .th-btn svg{width:19px;height:19px}
    .th-scrim{position:fixed;inset:0;z-index:300;background:rgba(4,6,14,.72);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);display:grid;align-items:end;justify-items:center;animation:thfade .2s}
    @keyframes thfade{from{opacity:0}}
    .th-sheet{width:min(520px,100%);max-height:86vh;overflow:auto;background:var(--night-2,#12172B);color:var(--fg,#F4F6FF);border:1px solid var(--line-2,rgba(255,255,255,.18));border-radius:22px 22px 0 0;padding:20px 18px calc(18px + env(safe-area-inset-bottom,0px));font:15px/1.5 var(--body,system-ui);box-shadow:0 -20px 60px rgba(0,0,0,.75);animation:thup .28s cubic-bezier(.2,.9,.3,1)}
    @media (min-width:600px){.th-scrim{align-items:center}.th-sheet{border-radius:22px}}
    @keyframes thup{from{transform:translateY(48px);opacity:0}}
    .th-sheet h2{font:700 24px/1.1 var(--display,sans-serif);margin:0 0 4px}
    .th-sheet p{margin:0 0 14px;color:var(--muted,#97A3C6);font-size:14px}
    .th-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    @media (max-width:440px){.th-grid{grid-template-columns:1fr}}
    .th-tile{position:relative;border:2px solid rgba(255,255,255,.1);border-radius:16px;padding:14px;cursor:pointer;text-align:start;color:#F4F6FF;min-height:108px;display:flex;flex-direction:column;justify-content:space-between;align-items:flex-start;gap:12px;font:inherit;transition:transform .14s,border-color .16s,box-shadow .18s}
    .th-tile:hover{transform:translateY(-2px);border-color:rgba(255,255,255,.28)}
    .th-tile.on{border-color:var(--gold,#FFC83D);box-shadow:0 0 24px -6px var(--tile-glow,rgba(255,200,61,.6))}
    .th-tile .dots{display:flex;gap:6px;flex:none}
    .th-tile .dots i{width:12px;height:12px;border-radius:50%;box-shadow:0 0 10px currentColor}
    .th-tile .info{display:grid;gap:3px;width:100%;min-width:0}
    .th-tile b{font-size:15.5px;line-height:1.25;font-family:var(--display,sans-serif)}
    .th-tile small{font-size:12.5px;line-height:1.35;color:rgba(244,246,255,.74)}
    .th-close{margin-top:16px;width:100%;border:0;background:var(--paper,#F5F7FF);color:var(--ink,#0D1122);border-radius:999px;padding:12px;font:700 15px var(--body,system-ui);cursor:pointer}`;

  let close = null;
  function open(){
    if(close) return;
    const scrim = document.createElement("div"); scrim.className = "th-scrim";
    scrim.innerHTML = `<div class="th-sheet" role="dialog" aria-label="Arcade theme"><h2>Arcade theme</h2><p>Only you see this. Applies across all 14 games on this device.</p>
      <div class="th-grid">${Object.entries(THEMES).map(([k, t]) => `<button type="button" class="th-tile ${k === theme ? "on" : ""}" data-th="${k}" style="background:radial-gradient(circle at 85% 15%,${t.lantern}30,transparent 60%),${t.night};--tile-glow:${t.lantern}" aria-pressed="${k === theme}">
        <span class="dots"><i style="background:${t.lantern};color:${t.lantern}"></i><i style="background:${t.gold};color:${t.gold}"></i><i style="background:${t.shrine};color:${t.shrine}"></i></span>
        <span class="info"><b>${t.name}</b><small>${t.note}</small></span></button>`).join("")}</div>
      <button type="button" class="th-close">Done</button></div>`;
    document.body.appendChild(scrim);
    close = () => { scrim.remove(); close = null; };
    scrim.onclick = e => {
      const th = e.target.closest("button[data-th]");
      if(th){
        theme = th.dataset.th; set("gn:arcadeTheme", theme); apply();
        if(window.Juice && Juice.sfx) Juice.sfx.click();
        scrim.querySelectorAll("button[data-th]").forEach(btn => {
          const on = btn.dataset.th === theme;
          btn.classList.toggle("on", on);
          btn.setAttribute("aria-pressed", String(on));
        });
        return;
      }
      if(e.target === scrim || e.target.closest(".th-close")) close();
    };
  }
  if(window.BackGuard) BackGuard.onBack(() => { if(close){ close(); return true; } return false; });

  const ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="13.5" cy="6.5" r=".8" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".8" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".8" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".8" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.5-.67 1.5-1.5 0-.39-.15-.74-.39-1.01-.23-.26-.38-.61-.38-.99 0-.83.67-1.5 1.5-1.5H16c3.31 0 6-2.69 6-6 0-4.96-4.49-9-10-9z"/></svg>`;
  function addButtons(){
    const slots = document.querySelectorAll("[data-theme-slot]");
    (slots.length ? slots : document.querySelectorAll("header.top, .bar .wrap, .hero")).forEach(h => {
      if(h.querySelector(":scope > .th-btn")) return;
      const b = document.createElement("button"); b.className = "th-btn"; b.type = "button"; b.title = "Arcade theme"; b.setAttribute("aria-label", "Arcade theme"); b.innerHTML = ICON;
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
