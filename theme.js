/* Site themes, picked by each player and saved on their device. A theme recolours every page
   (background, glow, accents, heading font) and lays a faint motif over the background. Each page
   names its colours differently, so PAGE maps the theme onto that page's own variables.
   Codenames also has card styles: by default the cards follow the theme, or a player picks one.
   Usage: load this script; it adds a palette button to the page header. Theme.cards() gives the card style. */
(function(){
  const svg = s => `url("data:image/svg+xml,${encodeURIComponent(s)}")`;
  const ball = (x, y, r, stars) => `<circle cx="${x}" cy="${y}" r="${r}" fill="#ff9a1f"/><circle cx="${x - r*.35}" cy="${y - r*.35}" r="${r*.28}" fill="#ffd9a0" opacity=".7"/>` +
    Array.from({length: stars}, (_, i)=>{ const a = i / stars * Math.PI * 2, d = stars > 1 ? r*.38 : 0; return `<path transform="translate(${x + Math.cos(a)*d} ${y + Math.sin(a)*d}) scale(${r/40})" d="M0-9 2.6-2.8 9-2.8 3.8 1 5.8 7.5 0 3.6-5.8 7.5-3.8 1-9-2.8-2.6-2.8z" fill="#d81e1e"/>`; }).join("");
  const THEMES = {
    default: {name:"Original", note:"Each game's own look"},
    dragonball: {name:"Dragon Ball", note:"Orange gi, seven balls", bg:"#0a1638", panel:"#10204a", glow1:"rgba(255,140,26,.22)", glow2:"rgba(255,210,63,.14)", a1:"#ff8c1a", a2:"#ffd23f", ink:"#2a1300",
      font:"Bangers", fontCss:"Bangers", motif: svg(`<svg xmlns="http://www.w3.org/2000/svg" width="260" height="260">${ball(40,50,16,4)}${ball(190,120,11,1)}${ball(110,215,13,7)}<path d="M0 160 L260 100" stroke="#ffd23f" stroke-width="1" opacity=".25"/></svg>`), motifOp:.14},
    conan: {name:"Detective Conan", note:"Navy blazer, red bowtie", bg:"#0b1430", panel:"#14204a", glow1:"rgba(224,36,47,.18)", glow2:"rgba(242,193,78,.12)", a1:"#e0242f", a2:"#f2c14e", ink:"#fff",
      font:"Special Elite", fontCss:"Special+Elite", motif: svg(`<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220"><g fill="none" stroke="#f2c14e" stroke-width="5" opacity=".9"><circle cx="70" cy="70" r="30"/><path d="M92 92 L130 130" stroke-linecap="round" stroke-width="9"/></g><path d="M150 170 l14 -8 l14 8 l-14 8z M178 170 l14 -8 l14 8 l-14 8z" fill="#e0242f"/><text x="20" y="200" font-family="serif" font-size="20" fill="#f2c14e" opacity=".8">?</text></svg>`), motifOp:.1},
    naruto: {name:"Naruto", note:"Hidden Leaf orange", bg:"#140b06", panel:"#24140a", glow1:"rgba(255,122,26,.22)", glow2:"rgba(255,64,64,.1)", a1:"#ff7a1a", a2:"#ffb25b", ink:"#2a1000",
      font:"Shojumaru", fontCss:"Shojumaru", motif: svg(`<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><path d="M60 60 m-22 0 a22 22 0 1 0 44 0 a16 16 0 1 0 -32 0 a10 10 0 1 0 20 0 a4 4 0 1 0 -8 0" fill="none" stroke="#ff7a1a" stroke-width="4"/><path d="M82 60 q30 -10 40 -40" fill="none" stroke="#ff7a1a" stroke-width="4"/><path d="M170 170 l20 -34 l20 34 z" fill="none" stroke="#ffb25b" stroke-width="3"/></svg>`), motifOp:.12},
    demonslayer: {name:"Demon Slayer", note:"Tanjiro's checker, Nezuko pink", bg:"#06120d", panel:"#0d1f17", glow1:"rgba(46,204,113,.18)", glow2:"rgba(255,126,182,.14)", a1:"#2ecc71", a2:"#ff7eb6", ink:"#03140a",
      font:"Kaisei Decol", fontCss:"Kaisei+Decol:wght@700", motif: svg(`<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56"><rect width="28" height="28" fill="#2ecc71"/><rect x="28" y="28" width="28" height="28" fill="#2ecc71"/></svg>`), motifOp:.06},
    onepiece: {name:"One Piece", note:"Straw hat on the Grand Line", bg:"#04203a", panel:"#082d50", glow1:"rgba(255,211,77,.18)", glow2:"rgba(227,52,47,.14)", a1:"#ffd34d", a2:"#e3342f", ink:"#2a1d00",
      font:"Pirata One", fontCss:"Pirata+One", motif: svg(`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80"><path d="M0 40 q25 -22 50 0 t50 0 t50 0 t50 0" fill="none" stroke="#7fd3ff" stroke-width="3"/></svg>`), motifOp:.1},
    jjk: {name:"Jujutsu Kaisen", note:"Cursed energy purple", bg:"#0b0614", panel:"#160d26", glow1:"rgba(138,92,255,.25)", glow2:"rgba(63,214,255,.14)", a1:"#8a5cff", a2:"#3fd6ff", ink:"#fff",
      font:"Russo One", fontCss:"Russo+One", motif: svg(`<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><g fill="none" stroke="#8a5cff" stroke-width="2"><circle cx="120" cy="120" r="40"/><circle cx="120" cy="120" r="70" stroke-dasharray="4 10"/><path d="M120 40 v160 M40 120 h160" stroke-dasharray="2 12"/></g></svg>`), motifOp:.12},
    sakura: {name:"Sakura night", note:"Soft pink petals", bg:"#160b16", panel:"#241227", glow1:"rgba(255,143,199,.22)", glow2:"rgba(255,209,232,.12)", a1:"#ff8fc7", a2:"#ffd1e8", ink:"#3a0a24",
      font:"Zen Maru Gothic", fontCss:"Zen+Maru+Gothic:wght@700", motif: svg(`<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220"><g fill="#ff8fc7"><path d="M40 40 c8 -14 22 -8 16 6 c14 2 10 18 -4 14 c0 14 -16 14 -14 0 c-14 2 -16 -14 -2 -14 c-6 -12 6 -18 4 -6z"/><path d="M170 150 c5 -9 14 -5 10 4 c9 1 6 11 -3 9 c0 9 -10 9 -9 0 c-9 1 -10 -9 -1 -9 c-4 -8 4 -11 3 -4z"/></g></svg>`), motifOp:.12},
  };
  const CARDS = {
    theme: {name:"Match my theme"},
    classic: {name:"Classic"},
    dragonball: {name:"Dragon Ball"},
    conan: {name:"Detective Conan"},
    naruto: {name:"Naruto"},
    demonslayer: {name:"Demon Slayer"},
    neon: {name:"Neon"},
  };
  // which of the page's own colour variables each theme colour lands on
  const PAGE = {
    hub:      {bg:"--bg", glow1:"--bg-glow1", glow2:"--bg-glow2", a1:"--accent", a2:"--accent2", ink:"--accent-ink", panel:"--panel-solid", font:"--display"},
    tierlist: {bg:"--bg", glow1:"--bg-glow1", glow2:"--bg-glow2", a1:"--accent", a2:"--accent2", ink:"--accent-ink", panel:"--panel-solid", font:"--display"},
    draw:     {bg:"--bg", glow1:"--bg-glow1", glow2:"--bg-glow2", a1:"--accent", a2:"--accent2", ink:"--accent-ink", panel:"--panel-solid", font:"--display"},
    codenames:{bg:"--bg", panel:"--bg2", a1:"--gold", font:"--display"},
    imposter: {bg:"--desk", panel:"--desk2", glow1:"--lamp", a1:"--amber", font:"--display"},
    werewolf: {bg:"--night1", panel:"--night2", a1:"--gold", font:"--display"},
  };
  const page = (location.pathname.replace(/^\//, "").split(/[/?]/)[0] || "hub").replace("index.html", "hub");
  const get = (k, d) => { try{ return localStorage.getItem(k) || d; }catch(e){ return d; } };
  const set = (k, v) => { try{ localStorage.setItem(k, v); }catch(e){} };
  let theme = THEMES[get("gn:theme", "default")] ? get("gn:theme", "default") : "default";
  let cards = CARDS[get("gn:cards", "theme")] ? get("gn:cards", "theme") : "theme";
  const listeners = [];

  const style = document.createElement("style");
  style.id = "gn-theme";
  function loadFont(t){
    if(!t.fontCss || document.querySelector(`link[data-font="${t.fontCss}"]`)) return;
    const l = document.createElement("link"); l.rel = "stylesheet"; l.dataset.font = t.fontCss;
    l.href = `https://fonts.googleapis.com/css2?family=${t.fontCss}&display=swap`; document.head.appendChild(l);
  }
  function apply(){
    const t = THEMES[theme], map = PAGE[page] || PAGE.hub;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.cards = cardStyle();
    if(page === "codenames") loadFont({fontCss: CARD_FONT[cardStyle()]});
    if(theme === "default"){ style.textContent = BASE; listeners.forEach(f=>f()); return; }
    loadFont(t);
    const vars = Object.entries(map).map(([k, v]) => k === "font" ? `${v}:"${t.font}",var(--fallback-display,system-ui),sans-serif` : t[k] ? `${v}:${t[k]}` : "").filter(Boolean).join(";");
    style.textContent = BASE + `html:root{${vars}}
      body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:radial-gradient(ellipse 70% 50% at 15% -5%,${t.glow1},transparent 65%),radial-gradient(ellipse 60% 45% at 100% 100%,${t.glow2},transparent 65%)}
      body::after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background-image:${t.motif};opacity:${t.motifOp};mix-blend-mode:screen}
      ${page === "werewolf" ? `body{background:linear-gradient(180deg,${t.bg},${t.panel})!important}` : ""}
      ${page === "imposter" ? `body{background:radial-gradient(ellipse 70% 55% at 50% 0%,${t.glow1},transparent 70%),linear-gradient(180deg,${t.panel},${t.bg})!important}` : ""}`;
    listeners.forEach(f=>f());
  }
  const CARD_FONT = {dragonball:"Bangers", conan:"Special+Elite", naruto:"Shojumaru", demonslayer:"Kaisei+Decol:wght@700"};
  function cardStyle(){ return cards === "theme" ? ({dragonball:"dragonball", conan:"conan", naruto:"naruto", demonslayer:"demonslayer", jjk:"neon", sakura:"neon"}[theme] || "classic") : cards; }

  const BASE = `.th-btn{width:34px;height:34px;border-radius:10px;border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.06);display:inline-grid;place-items:center;padding:0;cursor:pointer;color:inherit;flex:none}
    .th-btn svg{width:18px;height:18px}
    .th-scrim{position:fixed;inset:0;z-index:300;background:rgba(0,0,0,.6);display:grid;align-items:end;justify-items:center;animation:thfade .2s}
    @keyframes thfade{from{opacity:0}}
    .th-sheet{width:min(560px,100%);max-height:86vh;overflow:auto;background:#10131d;color:#eef1fa;border:1px solid rgba(255,255,255,.14);border-radius:20px 20px 0 0;padding:16px 16px calc(18px + env(safe-area-inset-bottom,0px));font:14px/1.45 Manrope,system-ui,sans-serif;animation:thup .3s cubic-bezier(.2,.9,.3,1)}
    @keyframes thup{from{transform:translateY(100%)}}
    .th-sheet h2{font:800 18px/1.2 Manrope,system-ui,sans-serif;margin:0 0 4px;letter-spacing:0;text-transform:none}
    .th-sheet h3{font:800 11px/1 Manrope,system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#8b93ad;margin:16px 0 8px}
    .th-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
    .th-tile{position:relative;border:2px solid transparent;border-radius:14px;padding:0;overflow:hidden;cursor:pointer;text-align:left;color:#fff;background:#222;min-height:86px;display:grid;align-content:end}
    .th-tile.on{border-color:#fff;box-shadow:0 0 0 3px rgba(255,255,255,.2)}
    .th-tile .sw{position:absolute;inset:0}
    .th-tile b{position:relative;display:block;padding:0 10px;font-size:15px;text-shadow:0 1px 4px rgba(0,0,0,.6)}
    .th-tile small{position:relative;display:block;padding:0 10px 9px;font-size:11px;opacity:.85;text-shadow:0 1px 4px rgba(0,0,0,.6)}
    .th-tile .dots{position:absolute;top:8px;right:8px;display:flex;gap:4px}
    .th-tile .dots i{width:12px;height:12px;border-radius:50%;border:1.5px solid rgba(255,255,255,.6)}
    .th-chips{display:flex;flex-wrap:wrap;gap:6px}
    .th-chips button{border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.05);color:#eef1fa;border-radius:999px;padding:7px 12px;font:700 13px Manrope,system-ui,sans-serif;cursor:pointer}
    .th-chips button.on{background:#eef1fa;color:#10131d}
    .th-close{margin-top:16px;width:100%;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.06);color:#eef1fa;border-radius:12px;padding:11px;font:800 14px Manrope,system-ui,sans-serif;cursor:pointer}`;

  let close = null;
  function open(){
    if(close) return;
    const scrim = document.createElement("div"); scrim.className = "th-scrim";
    const draw = ()=>{
      scrim.innerHTML = `<div class="th-sheet" role="dialog" aria-label="Theme"><h2>Your theme</h2><p style="margin:0;color:#8b93ad">Only you see it. It changes every game on this device.</p>
        <h3>Site theme</h3><div class="th-grid">${Object.entries(THEMES).map(([k, t])=>`<button class="th-tile ${k===theme?"on":""}" data-th="${k}">
          <span class="sw" style="background:${t.bg ? `radial-gradient(circle at 20% 0%,${t.glow1},transparent 70%),${t.motif} center/90px,linear-gradient(160deg,${t.panel},${t.bg})` : "linear-gradient(135deg,#0b0d14,#1b2240 50%,#3a1020)"}"></span>
          <span class="dots">${t.a1 ? `<i style="background:${t.a1}"></i><i style="background:${t.a2}"></i>` : ""}</span>
          <b style="${t.font ? `font-family:'${t.font}',system-ui;font-size:17px` : ""}">${t.name}</b><small>${t.note}</small></button>`).join("")}</div>
        <h3>Codenames cards</h3><div class="th-chips">${Object.entries(CARDS).map(([k, c])=>`<button data-cards="${k}" class="${k===cards?"on":""}">${c.name}</button>`).join("")}</div>
        <button class="th-close">Done</button></div>`;
      Object.values(THEMES).forEach(loadFont);
    };
    draw();
    document.body.appendChild(scrim);
    close = ()=>{ scrim.remove(); close = null; };
    scrim.onclick = e=>{
      // buttons only: the page itself carries data-cards (the current card style), so a bare [data-cards] matches every tap
      const th = e.target.closest("button[data-th]"), cd = e.target.closest("button[data-cards]");
      if(th){ theme = th.dataset.th; set("gn:theme", theme); apply(); draw(); return; }
      if(cd){ cards = cd.dataset.cards; set("gn:cards", cards); apply(); draw(); return; }
      if(e.target === scrim || e.target.closest(".th-close")) close();
    };
  }
  if(window.BackGuard) BackGuard.onBack(()=>{ if(close){ close(); return true; } return false; });

  // a palette button in whatever header the page has
  const ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3a9 9 0 100 18c1.2 0 1.6-1 1.2-1.8-.6-1.2.2-2.4 1.5-2.4H17a4 4 0 004-4C21 7 17 3 12 3z"/><circle cx="7.5" cy="11" r="1.2" fill="currentColor"/><circle cx="10.5" cy="7.5" r="1.2" fill="currentColor"/><circle cx="15" cy="7.5" r="1.2" fill="currentColor"/></svg>`;
  function addButtons(){
    const slots = document.querySelectorAll("[data-theme-slot]");  // a page can say exactly where the button goes
    (slots.length ? slots : document.querySelectorAll("header.top, .bar .wrap, .hero")).forEach(h=>{
      if(h.querySelector(":scope > .th-btn")) return;
      const b = document.createElement("button"); b.className = "th-btn"; b.type = "button"; b.title = "Theme"; b.setAttribute("aria-label", "Theme"); b.innerHTML = ICON;
      b.onclick = open;
      if(h.classList.contains("hero")){ b.style.cssText = "position:absolute;top:0;right:0"; if(getComputedStyle(h).position === "static") h.style.position = "relative"; }
      const before = h.querySelector(":scope > #soundBtn, :scope > .timer");
      before ? h.insertBefore(b, before) : h.appendChild(b);
    });
  }
  document.head.appendChild(style);
  apply();
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", addButtons); else addButtons();

  window.Theme = {open, cards: cardStyle, onChange: f=>listeners.push(f), get: ()=>theme};
})();
