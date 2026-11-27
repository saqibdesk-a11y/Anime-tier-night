/* Shared room bar for every game: live online/offline presence dots, 20s host-offline takeover vote,
   manual Pass Host, Sit-out / Watch toggle, and "Switch Stall Together" (moves the whole Discord group
   into another game with names and avatars intact).
   Usage: RoomBar.mount({act, game, onHostChange});
          RoomBar.update(room, me, hostKey) on every poll update. */
(function(){
  const PREFIX = {
    codenames: "cn:", lantern: "ll:", forged: "fb:", scroll: "bs:",
    silhouette: "sil:", dial: "dl:", clash: "cc:", bluff: "fb2:", mask: "mk:",
    werewolf: "ww:", imposter: "imp:", tierlist: "atn:", draw: "draw:",
  };
  const STALLS = [
    ["codenames", "Codenames", "#F2603A"],
    ["lantern", "Last Lantern", "#3F6FD8"],
    ["forged", "Forged Brush", "#7A4BC7"],
    ["scroll", "Broken Scroll", "#D6456B"],
    ["silhouette", "Silhouette", "#1E7F9E"],
    ["dial", "Festival Dial", "#E07A2F"],
    ["clash", "Caption Clash", "#C93B8E"],
    ["bluff", "Fox's Bluff", "#B53535"],
    ["mask", "Forehead Mask", "#2B8C82"],
    ["werewolf", "Werewolf", "#1E1A2E"],
    ["imposter", "Imposter", "#D9A441"],
    ["tierlist", "Tier List", "#C9962B"],
    ["draw", "Draw It", "#2E8B6E"],
  ];

  const css = `
  .rb-btn{position:relative;width:40px;height:40px;border-radius:50%;border:1px solid var(--line-2,rgba(243,235,221,.28));background:none;display:inline-grid;place-items:center;padding:0;cursor:pointer;color:inherit;flex:none}
  .rb-btn svg{width:20px;height:20px}
  .rb-btn i{position:absolute;top:2px;right:2px;width:9px;height:9px;border-radius:50%;background:var(--gold,#D9A441);border:2px solid var(--night,#1B1F4B)}
  .rb-btn i.urg{background:#FF4D6D;animation:rbpulse 1s infinite}
  @keyframes rbpulse{50%{transform:scale(1.3)}}
  .rb-off{opacity:.48!important;filter:grayscale(.65)}
  .rb-wrap{width:min(820px,100%);margin:6px auto 0;padding:0 max(12px,env(safe-area-inset-left,0px));display:grid;gap:8px;position:relative;z-index:15}
  .rb-banner{border-radius:14px;padding:11px 14px;display:grid;gap:9px;font:600 14px/1.4 var(--body,system-ui);box-shadow:0 10px 28px -12px rgba(0,0,0,.7);animation:rbfade .25s}
  .rb-banner.warn{background:color-mix(in srgb,#E0473F 22%,var(--night-2,#252A5E));border:1.5px solid #FF8A7A;color:var(--fg,#F3EBDD)}
  .rb-banner.info{background:color-mix(in srgb,var(--gold,#D9A441) 16%,var(--night-2,#252A5E));border:1.5px solid var(--gold,#D9A441);color:var(--fg,#F3EBDD);display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
  .rb-vrow{display:flex;flex-wrap:wrap;gap:7px}
  .rb-vbtn{display:inline-flex;align-items:center;gap:6px;border:1.5px solid var(--line-2,rgba(243,235,221,.3));background:rgba(0,0,0,.25);color:inherit;border-radius:999px;padding:4px 12px 4px 5px;font:700 13px var(--body,system-ui);cursor:pointer}
  .rb-vbtn.on{border-color:var(--gold,#D9A441);background:color-mix(in srgb,var(--gold,#D9A441) 24%,transparent)}
  .rb-vbtn .av{width:24px;height:24px;border-radius:50%;overflow:hidden;display:grid;place-items:center;background:var(--gold,#D9A441);color:#1E1A2E;font-size:11px;font-weight:900}
  .rb-vbtn .av img{width:100%;height:100%;object-fit:cover;object-position:50% 20%}
  .rb-vbtn b{background:var(--gold,#D9A441);color:#1E1A2E;border-radius:999px;padding:0 6px;font-size:11px}
  .rb-pill{border:0;border-radius:999px;padding:6px 13px;background:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E);font:800 13px var(--body,system-ui);cursor:pointer}
  .rb-scrim{position:fixed;inset:0;z-index:260;background:rgba(8,9,24,.64);display:grid;align-items:end;justify-items:center;animation:rbfade .2s}
  @media (min-width:640px){.rb-scrim{align-items:center}}
  @keyframes rbfade{from{opacity:0}}
  .rb-sheet{width:min(540px,100%);max-height:86vh;overflow:auto;background:var(--paper,#F3EBDD);color:var(--ink,#1E1A2E);border-radius:20px 20px 0 0;padding:18px 18px calc(18px + env(safe-area-inset-bottom,0px));font:15px/1.45 var(--body,system-ui);display:grid;gap:14px;animation:rbup .28s cubic-bezier(.2,.9,.3,1)}
  @media (min-width:640px){.rb-sheet{border-radius:20px}}
  @keyframes rbup{from{transform:translateY(50px);opacity:0}}
  .rb-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
  .rb-head h2{font:400 26px/1.1 var(--display,serif);margin:0}
  .rb-x{border:0;background:rgba(30,26,46,.1);color:inherit;width:36px;height:36px;border-radius:50%;font-size:20px;cursor:pointer}
  .rb-sec{display:grid;gap:8px;border-top:1px solid rgba(30,26,46,.12);padding-top:12px}
  .rb-sec h3{font:800 13px var(--body,system-ui);text-transform:uppercase;letter-spacing:.07em;color:var(--ink-2,#5B5670);margin:0}
  .rb-list{display:grid;gap:7px}
  .rb-row{display:flex;align-items:center;gap:10px;background:rgba(30,26,46,.05);border-radius:12px;padding:7px 10px}
  .rb-row .av{position:relative;width:34px;height:34px;border-radius:50%;overflow:hidden;display:grid;place-items:center;background:var(--gold,#D9A441);color:#1E1A2E;font-weight:900;font-size:14px;flex:none}
  .rb-row .av img{width:100%;height:100%;object-fit:cover;object-position:50% 20%}
  .rb-dot{width:9px;height:9px;border-radius:50%;flex:none}
  .rb-dot.on{background:#1FA971} .rb-dot.off{background:#9A96AE}
  .rb-row .nm{flex:1;min-width:0;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .rb-tag{font-size:11px;font-weight:800;border-radius:999px;padding:2px 8px;background:rgba(30,26,46,.1);color:var(--ink-2,#5B5670)}
  .rb-tag.host{background:var(--gold,#D9A441);color:#1E1A2E}
  .rb-tag.off{background:#E8D5D5;color:#9E2A2B}
  .rb-act{border:1px solid rgba(30,26,46,.22);background:#fff;color:var(--ink,#1E1A2E);border-radius:999px;padding:4px 10px;font:700 12px var(--body,system-ui);cursor:pointer}
  .rb-act.sure{background:#E0473F;border-color:#E0473F;color:#fff}
  .rb-toggle{display:flex;align-items:center;justify-content:space-between;gap:12px;background:rgba(30,26,46,.05);border-radius:14px;padding:10px 12px}
  .rb-toggle small{display:block;font-size:12px;color:var(--ink-2,#5B5670)}
  .rb-sw{width:50px;height:28px;border-radius:999px;border:0;background:#B7B2C9;position:relative;flex:none;cursor:pointer;transition:background .2s}
  .rb-sw::after{content:"";position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;background:#fff;transition:transform .2s}
  .rb-sw.on{background:var(--lantern,#F2603A)} .rb-sw.on::after{transform:translateX(22px)}
  .rb-stalls{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  .rb-stall{border:0;border-radius:12px;padding:10px 12px;font:800 14px var(--body,system-ui);color:#F3EBDD;text-align:left;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:6px;transition:transform .12s}
  .rb-stall:active{transform:scale(.97)}
  .rb-stall.cur{opacity:.45;cursor:default}
  .rb-stall.sure{outline:3px solid var(--ink,#1E1A2E);outline-offset:1px}
  .rb-close{width:100%;border:0;border-radius:999px;padding:12px;background:var(--ink,#1E1A2E);color:var(--paper,#F3EBDD);font:800 15px var(--body,system-ui);cursor:pointer}`;
  const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`;

  let act = null, game = "", onHostChange = null, room = null, me = null, hostKey = null;
  let btn = null, bannerWrap = null, scrim = null, redirecting = false, bannerSig = "";

  const pic = p => {
    const src = window.Avatars && p ? Avatars.src(p) : null;
    return src ? `<img src="${esc(src)}" alt="">` : esc(((p && p.name) || "?")[0].toUpperCase());
  };

  function ensureUI(){
    if(!btn){
      const hdr = document.querySelector("header.top, .bar .wrap");
      if(hdr){
        btn = document.createElement("button");
        btn.type = "button"; btn.className = "rb-btn"; btn.hidden = true;
        btn.title = "Players & Room"; btn.setAttribute("aria-label", "Players and Room controls");
        btn.innerHTML = ICON + '<i hidden></i>';
        btn.onclick = openSheet;
        const before = hdr.querySelector(":scope > .th-btn, :scope > #soundBtn, :scope > .timer");
        before ? hdr.insertBefore(btn, before) : hdr.appendChild(btn);
      }
    }
    if(!bannerWrap){
      bannerWrap = document.createElement("div");
      bannerWrap.className = "rb-wrap";
      const hdr = document.querySelector("header.top, .bar");
      if(hdr && hdr.parentNode) hdr.parentNode.insertBefore(bannerWrap, hdr.nextSibling);
      else document.body.prepend(bannerWrap);
    }
  }

  function mount(opts){
    act = opts.act; game = opts.game || ""; onHostChange = opts.onHostChange || null;
    if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", ensureUI);
    else ensureUI();
    if(window.BackGuard) BackGuard.onBack(() => { if(!scrim) return false; closeSheet(); return true; });
    document.addEventListener("keydown", e => { if(e.key === "Escape" && scrim) closeSheet(); });
  }

  function saveCreds(g, code, m, hk){
    const pref = PREFIX[g]; if(!pref) return;
    try{ localStorage.setItem(pref + code, JSON.stringify({me: m || null, hostKey: hk || null})); }catch(e){}
  }

  function isSittingOutNow(r, pid){
    const p = r.players && r.players[pid];
    if(!p) return false;
    if(r.phase === "lobby" || r.phase === "final" || r.phase === "gallery") return false;
    if(p.sitout || p.spectator) return true;
    if((r.game === "lantern" || r.game === "bluff" || r.game === "mask") && r.table && Array.isArray(r.table.order) && !r.table.order.includes(pid)) return true;
    return false;
  }

  function update(r, m, hk){
    ensureUI();
    room = r; me = m; hostKey = hk || null;
    const joined = !!(me && room && room.players && room.players[me.pid]);
    if(btn) btn.hidden = !joined;
    if(!room){ if(bannerWrap) bannerWrap.innerHTML = ""; return; }

    // 1. Switch Stall Together redirect!
    if(room.movedTo && room.movedTo.code && !redirecting){
      redirecting = true;
      const mv = room.movedTo;
      if(me) saveCreds(mv.game, mv.code, me, mv.hostKey || null);
      location.href = `/${mv.game}?room=${mv.code}`;
      return;
    }

    const meta = room.roomMeta || {};

    // 2. Host takeover / Pass Host live sync (grant new hostKey or clear revoked hostKey)
    if(joined && meta.newHostKey && meta.newHostKey !== hostKey){
      hostKey = meta.newHostKey;
      saveCreds(game || room.game || "tierlist", room.code, me, hostKey);
      if(onHostChange) onHostChange(hostKey, true);
    } else if(joined && hostKey && meta.hostPid && meta.hostPid !== me.pid && meta.isHost === false){
      hostKey = null;
      saveCreds(game || room.game || "tierlist", room.code, me, null);
      if(onHostChange) onHostChange(null, false);
    }

    // 3. Dim offline avatars across the page
    const onlineSet = new Set(meta.online || []);
    if(onlineSet.size){
      document.querySelectorAll("[data-pid]").forEach(el => {
        const pid = el.dataset.pid;
        if(room.players[pid]) el.classList.toggle("rb-off", !onlineSet.has(pid));
      });
    }

    // 4. Header button indicator dot
    if(btn && joined){
      const dot = btn.querySelector("i");
      const anyOffline = Object.keys(room.players).some(pid => !onlineSet.has(pid));
      dot.hidden = !(meta.hostOffline || anyOffline);
      dot.classList.toggle("urg", !!meta.hostOffline);
    }

    // 5. Floating banners (20s Host Offline Vote + Watching/Sit-out)
    renderBanners(meta, onlineSet, joined);
    if(scrim) drawSheet();
  }

  function renderBanners(meta, onlineSet, joined){
    if(!bannerWrap) return;
    if(!joined){ bannerWrap.innerHTML = ""; bannerSig = ""; return; }
    const wantOut = (meta.wantSitout || []).includes(me.pid);
    const watching = isSittingOutNow(room, me.pid);
    const showVote = !!(meta.hostOffline && meta.hostPid !== me.pid);
    const votes = meta.hostVotes || {}, myVote = votes[me.pid];
    const sig = JSON.stringify([showVote, meta.hostPid, votes, meta.hostVoteNeed, [...onlineSet].sort(), wantOut, watching]);
    if(sig === bannerSig) return;
    bannerSig = sig;
    let html = "";
    if(showVote){
      const hName = (room.players[meta.hostPid] || {}).name || "The host";
      const cands = Object.keys(room.players).filter(pid => pid !== meta.hostPid && onlineSet.has(pid));
      const tally = pid => Object.values(votes).filter(t => t === pid).length;
      html += `<div class="rb-banner warn">
        <div><b>${esc(hName)}</b> has been offline for 20s+. Vote for a new host (need ${meta.hostVoteNeed} vote${meta.hostVoteNeed===1?"":"s"} — old host gets kicked and can rejoin later):</div>
        <div class="rb-vrow">${cands.map(pid => {
          const n = tally(pid);
          return `<button type="button" class="rb-vbtn ${myVote===pid?"on":""}" data-rb-vote="${esc(pid)}"><span class="av">${pic(room.players[pid])}</span>${esc(room.players[pid].name)}${pid===me.pid?" (you)":""}${n?`<b>${n}</b>`:""}</button>`;
        }).join("")}</div></div>`;
    }
    if(watching || wantOut){
      const msg = wantOut
        ? (watching ? "You're sitting out this round. You can still chat and throw pranks!" : "You'll sit out the next round.")
        : "You joined mid-round — sit tight and you'll be dealt in automatically next round!";
      html += `<div class="rb-banner info"><span>${msg}</span>${wantOut ? '<button type="button" class="rb-pill" data-rb-sit="0">Jump back in</button>' : ""}</div>`;
    }
    bannerWrap.innerHTML = html;
  }

  function openSheet(){
    if(scrim || !room || !me) return;
    scrim = document.createElement("div"); scrim.className = "rb-scrim";
    document.body.appendChild(scrim);
    drawSheet();
    scrim.onclick = handleSheetClick;
  }
  function closeSheet(){ if(scrim){ scrim.remove(); scrim = null; } }

  function drawSheet(){
    if(!scrim || !room || !me) return;
    const meta = room.roomMeta || {}, onlineSet = new Set(meta.online || []);
    const wantOut = (meta.wantSitout || []).includes(me.pid);
    const isHost = !!(hostKey || meta.isHost);
    const curGame = game || room.game || "tierlist";
    const pids = Object.keys(room.players);
    scrim.innerHTML = `<div class="rb-sheet" role="dialog" aria-label="Room & Players">
      <div class="rb-head"><h2>Room ${esc(room.code)}</h2><button type="button" class="rb-x" data-rb-close aria-label="Close">×</button></div>
      <div class="rb-toggle">
        <div><b>Sit out next round</b><small>Stay in the room to watch, chat and throw pranks without being dealt in.</small></div>
        <button type="button" class="rb-sw ${wantOut?"on":""}" data-rb-sit="${wantOut?0:1}" aria-pressed="${wantOut}" aria-label="Sit out next round"></button>
      </div>
      <div class="rb-sec"><h3>Players (${onlineSet.size}/${pids.length} online)</h3>
        <div class="rb-list">${pids.map(pid => {
          const p = room.players[pid], on = onlineSet.has(pid), isH = pid === meta.hostPid, out = (meta.wantSitout||[]).includes(pid);
          return `<div class="rb-row"><span class="rb-dot ${on?"on":"off"}" title="${on?"Online":"Offline"}"></span>
            <span class="av">${pic(p)}</span><span class="nm">${esc(p.name)}${pid===me.pid?" (you)":""}</span>
            ${isH?'<span class="rb-tag host">Host</span>':""}
            ${!on?'<span class="rb-tag off">Offline</span>':""}
            ${out?'<span class="rb-tag">Sitting out</span>':""}
            ${isHost && pid !== me.pid ? `<button type="button" class="rb-act" data-rb-pass="${esc(pid)}">Make host</button>` : ""}
          </div>`;
        }).join("")}</div></div>
      ${isHost ? `<div class="rb-sec"><h3>Switch stall together</h3>
        <p style="margin:0;font-size:13px;color:var(--ink-2,#5B5670)">Moves everyone in this room into a new game together with their names and avatars.</p>
        <div class="rb-stalls">${STALLS.map(([id, label, col]) =>
          `<button type="button" class="rb-stall ${id===curGame?"cur":""}" data-rb-switch="${id}" style="background:${col}" ${id===curGame?"disabled":""}><span>${label}</span><span>${id===curGame?"Here":"→"}</span></button>`
        ).join("")}</div></div>` : ""}
      <button type="button" class="rb-close" data-rb-close>Done</button>
    </div>`;
  }

  async function handleSheetClick(e){
    if(e.target === scrim || e.target.closest("[data-rb-close]")){ closeSheet(); return; }
    const sit = e.target.closest("[data-rb-sit]");
    if(sit){ try{ await act("sitout", {sitout: sit.dataset.rbSit === "1"}); }catch(err){ alert(err.message); } return; }
    const pass = e.target.closest("[data-rb-pass]");
    if(pass){
      if(pass.dataset.sure !== "1"){ pass.dataset.sure = "1"; pass.classList.add("sure"); pass.textContent = "Confirm?"; return; }
      try{ await act("passhost", {target: pass.dataset.rbPass}); closeSheet(); }catch(err){ alert(err.message); }
      return;
    }
    const sw = e.target.closest("[data-rb-switch]");
    if(sw && !sw.disabled){
      if(sw.dataset.sure !== "1"){
        scrim.querySelectorAll("[data-rb-switch]").forEach(x => { x.dataset.sure = ""; x.classList.remove("sure"); const sp = x.querySelector("span:last-child"); if(sp && !x.disabled) sp.textContent = "→"; });
        sw.dataset.sure = "1"; sw.classList.add("sure"); sw.querySelector("span:last-child").textContent = "Go!";
        return;
      }
      try{
        const res = await act("switchgame", {to: sw.dataset.rbSwitch});
        if(res && res.code){
          saveCreds(res.game, res.code, me, res.hostKey || null);
          redirecting = true;
          location.href = `/${res.game}?room=${res.code}`;
        }
      }catch(err){ alert(err.message); }
    }
  }

  document.addEventListener("click", async e => {
    const v = e.target.closest("[data-rb-vote]");
    if(v && act){ try{ await act("votehost", {target: v.dataset.rbVote}); }catch(err){ alert(err.message); } return; }
    const sit = e.target.closest(".rb-banner [data-rb-sit]");
    if(sit && act){ try{ await act("sitout", {sitout: sit.dataset.rbSit === "1"}); }catch(err){ alert(err.message); } }
  });

  window.RoomBar = {mount, update, open: openSheet, close: closeSheet};
})();
