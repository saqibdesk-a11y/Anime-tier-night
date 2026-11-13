/* The chat every game shares. A round button opens a sheet from the bottom on phones and a panel
   on bigger screens. The server decides who reads and writes which channel (room.chat, chatRead,
   chatWrite, chatNames, chatWhy); this file only draws it and posts messages.
   Usage: Chat.mount({act}) once, where act(action, body) posts to the room as you;
          Chat.update(room, me) after every room update (me = {pid} or null). */
(function(){
  const css = `
  .fc-fab{position:fixed;right:max(14px,env(safe-area-inset-right,0px));bottom:calc(var(--chat-lift,0px) + 16px + env(safe-area-inset-bottom,0px));z-index:35;width:56px;height:56px;border-radius:50%;border:2px solid var(--night,#1B1F4B);background:var(--lantern,#F2603A);color:var(--on-lantern,#1E1A2E);display:grid;place-items:center;cursor:pointer;box-shadow:0 10px 26px -8px rgba(0,0,0,.7);transition:transform .15s}
  .fc-fab:active{transform:scale(.92)}
  .fc-fab svg{width:25px;height:25px}
  .fc-fab b{position:absolute;top:-5px;right:-5px;min-width:22px;height:22px;border-radius:999px;background:var(--gold,#D9A441);color:#1E1A2E;font:700 12px/22px var(--body,system-ui);text-align:center;padding:0 6px;border:2px solid var(--night,#1B1F4B)}
  .fc{position:fixed;left:0;right:0;bottom:0;z-index:46;height:min(70dvh,600px);display:flex;flex-direction:column;background:var(--night-2,#252A5E);color:var(--fg,#F3EBDD);border-top:3px solid var(--lantern,#F2603A);border-radius:18px 18px 0 0;box-shadow:0 -24px 60px -10px rgba(0,0,0,.7);font-family:var(--body,system-ui);animation:fcup .28s cubic-bezier(.2,.9,.3,1)}
  @keyframes fcup{from{transform:translateY(100%)}}
  @media (min-width:760px){.fc{left:auto;right:16px;bottom:calc(var(--chat-lift,0px) + 16px);width:380px;height:min(600px,calc(100dvh - 100px - var(--chat-lift,0px)));border-radius:16px;border:1px solid var(--line-2,rgba(243,235,221,.28));border-top:3px solid var(--lantern,#F2603A)}}
  .fc.typing{top:var(--kb-top,0px);bottom:var(--kb-bottom,0px);height:auto;border-radius:0;animation:none}
  .fc header{display:flex;align-items:center;gap:6px;padding:10px 10px 8px 14px;flex:none}
  .fc .fc-tabs{display:flex;gap:6px;flex:1;overflow-x:auto;scrollbar-width:none}
  .fc .fc-tabs button{flex:none;position:relative;border:1px solid var(--line-2,rgba(243,235,221,.28));background:none;color:var(--muted,#A9A6C8);border-radius:999px;padding:6px 13px;font:700 14px var(--body,system-ui);cursor:pointer}
  .fc .fc-tabs button.on{background:var(--paper,#F3EBDD);border-color:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E)}
  .fc .fc-tabs button i{position:absolute;top:1px;right:3px;width:8px;height:8px;border-radius:50%;background:var(--lantern,#F2603A)}
  .fc .fc-x{border:0;background:rgba(255,255,255,.08);color:inherit;border-radius:50%;width:38px;height:38px;font-size:20px;cursor:pointer;flex:none}
  .fc .fc-msgs{flex:1 1 auto;min-height:0;overflow-y:auto;padding:4px 12px 12px;display:flex;flex-direction:column;gap:8px;overscroll-behavior:contain}
  .fc .fc-m{display:grid;grid-template-columns:30px minmax(0,1fr);gap:8px;align-items:end;max-width:86%}
  .fc .fc-av{width:30px;height:30px;border-radius:50%;overflow:hidden;display:grid;place-items:center;font:700 13px var(--body,system-ui);color:#1E1A2E;background:var(--gold,#D9A441)}
  .fc .fc-av img{width:100%;height:100%;object-fit:cover;object-position:top}
  .fc .fc-b{background:rgba(243,235,221,.09);border-radius:14px 14px 14px 4px;padding:7px 11px;overflow-wrap:anywhere;font-size:15px;line-height:1.45}
  .fc .fc-b span{display:block;font-size:12px;font-weight:700;color:var(--gold,#D9A441);margin-bottom:1px}
  .fc .fc-m.fc-mine{align-self:flex-end;grid-template-columns:minmax(0,1fr)}
  .fc .fc-m.fc-mine .fc-av,.fc .fc-m.fc-mine .fc-b span{display:none}
  .fc .fc-m.fc-mine .fc-b{background:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E);border-radius:14px 14px 4px 14px}
  .fc .fc-sys{align-self:center;max-width:94%;text-align:center;font-size:13px;color:var(--muted,#A9A6C8);padding:2px 10px}
  .fc .fc-empty{margin:auto;color:var(--muted,#A9A6C8);text-align:center;font-size:15px;padding:20px}
  .fc form{display:flex;align-items:flex-end;gap:6px;padding:8px 10px calc(8px + env(safe-area-inset-bottom,0px));border-top:1px solid var(--line,rgba(243,235,221,.14));flex:none}
  .fc.typing form{padding-bottom:8px}
  .fc textarea{flex:1;min-width:0;height:40px;max-height:120px;resize:none;overflow-y:auto;background:var(--night,#1B1F4B);border:1px solid var(--line-2,rgba(243,235,221,.28));border-radius:20px;padding:9px 14px;font:16px/1.3 var(--body,system-ui);color:inherit;outline:none;display:block}
  .fc textarea:focus{border-color:var(--lantern,#F2603A)}
  .fc form button{border:0;border-radius:50%;width:40px;height:40px;flex:none;background:var(--lantern,#F2603A);color:var(--on-lantern,#1E1A2E);display:grid;place-items:center;cursor:pointer}
  .fc form button svg{width:18px;height:18px}
  .fc .fc-locked{flex:1;color:var(--muted,#A9A6C8);font-size:14px;text-align:center;padding:8px}
  @media (prefers-reduced-motion:reduce){.fc{animation:none}}`;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>';
  const SEND = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 20.5 21 12 3 3.5 3 10l12 2-12 2z"/></svg>';

  let act = null, room = null, me = null, open = false, ch = null, seen = {}, sig = "", formSig = "";
  const fab = document.createElement("button");
  fab.className = "fc-fab"; fab.type = "button"; fab.hidden = true; fab.setAttribute("aria-label", "Open chat");
  fab.innerHTML = ICON + '<b hidden></b>';
  const box = document.createElement("section");
  box.className = "fc"; box.hidden = true; box.setAttribute("aria-label", "Chat");
  box.innerHTML = '<header><div class="fc-tabs"></div><button class="fc-x" type="button" aria-label="Close chat">×</button></header><div class="fc-msgs" aria-live="polite"></div><form></form>';
  const $ = s => box.querySelector(s);

  function mount(opts){
    act = opts.act;
    document.body.append(fab, box);
    if(window.BackGuard) BackGuard.onBack(()=>{ if(!open) return false; close(); return true; });
  }
  const pic = p => window.Avatars && p ? Avatars.src(p) : null;
  const name = c => (room.chatNames || {})[c] || "Everyone";

  function update(r, m){
    room = r; me = m;
    const joined = !!(me && room && room.players && room.players[me.pid]);
    const read = (room && room.chatRead) || [];
    fab.hidden = !joined || !read.length || open;
    if(!joined || !read.length){ box.hidden = true; open = false; return; }
    // land on a channel you can write in (the ghosts' chat once you're dead, say)
    if(!read.includes(ch)) ch = read.find(c => (room.chatWrite || []).includes(c)) || read[0];
    const msgs = room.chat || [];
    const inCh = c => msgs.filter(x => x.ch === c || x.ch === "*");
    const last = c => { const l = inCh(c).slice(-1)[0]; return l ? l.id : null; };
    if(open) seen[ch] = last(ch);
    const unread = read.reduce((n, c)=>{
      if(open && c === ch) return n;
      const list = msgs.filter(x => x.ch === c), i = list.findIndex(x => x.id === seen[c]);
      return n + list.slice(i + 1).filter(x => x.pid && x.pid !== me.pid).length;
    }, 0);
    const badge = fab.querySelector("b"); badge.hidden = !unread; badge.textContent = unread > 99 ? "99+" : unread;
    box.hidden = !open;
    if(!open) return;
    $(".fc-tabs").innerHTML = read.map(c => {
      const dot = c !== ch && msgs.some(x => x.ch === c && x.pid && x.pid !== me.pid) && last(c) !== seen[c];
      return `<button type="button" class="${c === ch ? "on" : ""}" data-ch="${esc(c)}">${esc(name(c))}${dot ? "<i></i>" : ""}</button>`;
    }).join("");
    const list = inCh(ch), write = (room.chatWrite || []).includes(ch);
    const s = ch + "|" + list.map(x => x.id).join(",");
    if(s !== sig){
      sig = s;
      const m = $(".fc-msgs"), atBottom = m.scrollHeight - m.scrollTop - m.clientHeight < 80;
      m.innerHTML = list.length ? list.map(x => {
        if(x.sys) return `<div class="fc-sys">${esc(x.text)}</div>`;
        const p = room.players[x.pid] || {name: x.name}, src = pic(p);
        return `<div class="fc-m ${x.pid === me.pid ? "fc-mine" : ""}"><span class="fc-av">${src ? `<img src="${esc(src)}" alt="">` : esc((x.name || "?")[0].toUpperCase())}</span><div class="fc-b"><span>${esc(x.name)}</span>${esc(x.text)}</div></div>`;
      }).join("") : `<div class="fc-empty">${read.length > 1 && ch !== read[0] ? `Only ${esc(name(ch).toLowerCase())} can read this.` : "No messages yet. Say hi."}</div>`;
      if(atBottom || (list.slice(-1)[0] || {}).pid === me.pid) m.scrollTop = m.scrollHeight;
    }
    // rebuild the input only when what you can write changes, so a phone keyboard stays open
    const why = room.chatWhy || "You can't write here right now.";
    const f = ch + "|" + write + "|" + why;
    if(f !== formSig){
      formSig = f;
      const keep = ($("textarea") || {}).value || "";
      $("form").innerHTML = write
        ? `<textarea rows="1" maxlength="300" autocomplete="off" enterkeyhint="send" placeholder="Message ${esc(name(ch).toLowerCase())}" aria-label="Message"></textarea><button aria-label="Send">${SEND}</button>`
        : `<div class="fc-locked">${esc(why)}</div>`;
      const t = $("textarea"); if(t){ t.value = keep; grow(); }
    }
  }
  function redraw(){ sig = ""; formSig = ""; if(room) update(room, me); }
  function show(){ open = true; redraw(); $(".fc-msgs").scrollTop = 1e9; }
  function close(){ const t = $("textarea"); t && t.blur(); open = false; redraw(); }
  function grow(){ const t = $("textarea"); if(!t) return; t.style.height = "40px"; t.style.height = Math.min(t.scrollHeight + 2, 120) + "px"; }

  fab.onclick = show;
  $(".fc-x").onclick = close;
  $(".fc-tabs").onclick = e => { const b = e.target.closest("[data-ch]"); if(!b) return; ch = b.dataset.ch; redraw(); $(".fc-msgs").scrollTop = 1e9; };
  box.addEventListener("input", e => { if(e.target.tagName === "TEXTAREA") grow(); });
  // Enter sends; Shift+Enter adds a new line
  box.addEventListener("keydown", e => { if(e.target.tagName === "TEXTAREA" && e.key === "Enter" && !e.shiftKey){ e.preventDefault(); $("form").requestSubmit(); } });
  // the send button must not take focus from the text box, or the phone keyboard closes on every message
  box.addEventListener("pointerdown", e => { if(e.target.closest("form button")) e.preventDefault(); });
  box.addEventListener("mousedown", e => { if(e.target.closest("form button")) e.preventDefault(); });
  box.addEventListener("submit", async e => {
    e.preventDefault();
    const t = $("textarea"), text = t && t.value.trim(); if(!text) return;
    t.value = ""; grow();
    try{ await act("chat", {ch, text}); }
    catch(err){ t.value = text; grow(); const m = $(".fc-msgs"); m.insertAdjacentHTML("beforeend", `<div class="fc-sys" style="color:var(--lantern,#F2603A)">${esc(err.message)}</div>`); m.scrollTop = 1e9; }
  });
  // phones shrink the visible area when the keyboard opens: keep the whole chat inside what's left
  (function fitToKeyboard(){
    const vv = window.visualViewport, small = () => !matchMedia("(min-width:760px)").matches;
    const fit = () => {
      const on = document.activeElement && box.contains(document.activeElement) && document.activeElement.tagName === "TEXTAREA" && small();
      box.classList.toggle("typing", !!on);
      if(!on) return;
      box.style.setProperty("--kb-top", (vv ? vv.offsetTop : 0) + "px");
      box.style.setProperty("--kb-bottom", (vv ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) : 0) + "px");
      $(".fc-msgs").scrollTop = 1e9;
    };
    if(vv){ vv.addEventListener("resize", fit); vv.addEventListener("scroll", fit); }
    window.addEventListener("resize", fit);
    box.addEventListener("focusin", () => { fit(); setTimeout(fit, 120); setTimeout(fit, 350); });
    box.addEventListener("focusout", () => setTimeout(fit, 120));
  })();

  // what changes with every chat message or prank; everything else is the game itself
  const SOCIAL = new Set(["chat", "chatRead", "chatWrite", "chatNames", "chatWhy", "pranks", "prankKinds", "prankWait",
                          "prankCooldown", "prankStats", "version", "now", "lastChat", "lastPrank"]);
  const gameSig = r => JSON.stringify(r, (k, v) => SOCIAL.has(k) ? undefined : v);
  // true when the newest update only brought chat or pranks, so the page can skip redrawing the game
  const socialOnly = (prev, next) => !!(prev && next) && gameSig(prev) === gameSig(next);

  window.Chat = {mount, update, open: show, close, isOpen: () => open, socialOnly};
})();
