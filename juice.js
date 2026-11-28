/* Shared Anime Arcade Juice Engine: rich multi-layered Web Audio synthesis inspired by
   Persona 5, Nintendo Switch, JRPG menus, and Japanese game shows (zero external files needed!),
   plus canvas confetti, radial neon bursts, screen shake, and global mute toggle. */
(function(){
  const REDUCED = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion:reduce)").matches;
  let ac = null;
  let muted = false;
  try{ muted = localStorage.getItem("gn:muted") === "1"; }catch(e){}

  function ctx(){
    if(muted) return null;
    if(!ac){
      const C = window.AudioContext || window.webkitAudioContext;
      if(!C) return null;
      ac = new C();
    }
    if(ac.state === "suspended") ac.resume().catch(()=>{});
    return ac;
  }

  // Warm bell/koto harmonic voice (fundamental + octave shimmer + optional filter sweep)
  function bell(freq, dur=0.22, vol=0.13, delay=0, slideTo=null, type="triangle"){
    const c = ctx(); if(!c) return;
    const t0 = c.currentTime + delay;
    const o1 = c.createOscillator(), o2 = c.createOscillator(), g = c.createGain();
    o1.type = type; o2.type = "sine";
    o1.frequency.setValueAtTime(freq, t0);
    o2.frequency.setValueAtTime(freq * 2.003, t0); // slight detuned anime shimmer
    if(slideTo){
      o1.frequency.exponentialRampToValueAtTime(Math.max(20, slideTo), t0 + dur);
      o2.frequency.exponentialRampToValueAtTime(Math.max(40, slideTo * 2.003), t0 + dur);
    }
    const g2 = c.createGain(); g2.gain.value = 0.35;
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.linearRampToValueAtTime(vol, t0 + 0.009);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o1.connect(g); o2.connect(g2); g2.connect(g); g.connect(c.destination);
    o1.start(t0); o2.start(t0);
    o1.stop(t0 + dur + 0.03); o2.stop(t0 + dur + 0.03);
  }

  // Filtered noise swoosh / percussive snap
  function sweepNoise(dur=0.12, vol=0.11, delay=0, fStart=900, fEnd=3800, q=1.8){
    const c = ctx(); if(!c) return;
    const t0 = c.currentTime + delay;
    const len = Math.max(1, Math.floor(c.sampleRate * dur));
    const buf = c.createBuffer(1, len, c.sampleRate);
    const data = buf.getChannelData(0);
    for(let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 1.3);
    const src = c.createBufferSource(); src.buffer = buf;
    const flt = c.createBiquadFilter(); flt.type = "bandpass"; flt.Q.value = q;
    flt.frequency.setValueAtTime(fStart, t0);
    flt.frequency.exponentialRampToValueAtTime(Math.max(60, fEnd), t0 + dur);
    const g = c.createGain();
    g.gain.setValueAtTime(vol, t0);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    src.connect(flt); flt.connect(g); g.connect(c.destination);
    src.start(t0);
  }

  // Punchy synth note through resonant lowpass (for Persona / arcade brass & buzzers)
  function synth(freq, dur=0.18, vol=0.12, delay=0, type="sawtooth", cutStart=2600, cutEnd=500, slideTo=null){
    const c = ctx(); if(!c) return;
    const t0 = c.currentTime + delay;
    const o = c.createOscillator(), flt = c.createBiquadFilter(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t0);
    if(slideTo) o.frequency.exponentialRampToValueAtTime(Math.max(20, slideTo), t0 + dur);
    flt.type = "lowpass"; flt.Q.value = 3.2;
    flt.frequency.setValueAtTime(cutStart, t0);
    flt.frequency.exponentialRampToValueAtTime(Math.max(120, cutEnd), t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.linearRampToValueAtTime(vol, t0 + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(flt); flt.connect(g); g.connect(c.destination);
    o.start(t0); o.stop(t0 + dur + 0.03);
  }

  const sfx = {
    // Crisp JRPG / Switch cursor sparkle-pip
    click(){
      bell(880, 0.065, 0.085, 0, 1174.66, "sine");
      sweepNoise(0.028, 0.04, 0, 3200, 5600, 2.5);
    },
    // Bouncy anime bubble-pop confirmation
    pop(){
      bell(587.33, 0.085, 0.10, 0, 880, "triangle");
      bell(1174.66, 0.09, 0.055, 0.025, 1318.5, "sine");
    },
    // Rapid crisp anime card-riffle deal
    deal(){
      sweepNoise(0.065, 0.11, 0, 1400, 4800, 1.5);
      bell(440, 0.055, 0.065, 0.01, 660, "triangle");
    },
    // Dramatic Yu-Gi-Oh / Persona card-whip + snap
    card(){
      sweepNoise(0.11, 0.14, 0, 700, 4200, 1.6);
      synth(220, 0.08, 0.11, 0.02, "triangle", 1400, 300, 95);
      bell(784, 0.11, 0.075, 0.035, 1046.5, "sine");
    },
    // Anime katana-flash / magic shimmer 3D flip ("SHING!")
    flip(){
      sweepNoise(0.14, 0.11, 0, 2200, 7400, 2.8);
      bell(1046.5, 0.18, 0.095, 0.01, 1567.98, "sine");
      bell(1567.98, 0.22, 0.07, 0.045, 2093, "sine");
    },
    // Japanese lacquer-wood / mahjong coaster clack!
    clack(){
      sweepNoise(0.032, 0.16, 0, 1900, 950, 3.2);
      synth(310, 0.065, 0.14, 0, "triangle", 1800, 380, 145);
      bell(940, 0.045, 0.06, 0, 760, "sine");
    },
    // Bright Persona / JRPG "Your Turn!" chime chord (D5 -> F#5 -> A5 -> D6)
    turn(){
      [587.33, 739.99, 880, 1174.66].forEach((f, i) => bell(f, 0.24, 0.105, i * 0.048, null, "triangle"));
    },
    // Anime time-rewind / record-whip reverse
    reverse(){
      sweepNoise(0.16, 0.12, 0, 3600, 700, 2.0);
      synth(660, 0.11, 0.11, 0, "sawtooth", 2400, 600, 310);
      synth(330, 0.16, 0.12, 0.09, "sawtooth", 900, 3400, 784);
    },
    // Anime Power-Up / Limit Break rising pentatonic harp-synth sweep!
    wild(){
      const notes = [523.25, 587.33, 659.25, 783.99, 880, 1046.5, 1318.5];
      notes.forEach((f, i) => bell(f, 0.22, 0.095, i * 0.038, null, "triangle"));
      sweepNoise(0.24, 0.09, 0.04, 1000, 6400, 2.2);
    },
    // Iconic Japanese Game-Show "BUBU!!" double wrong buzzer
    warn(){
      [0, 0.135].forEach(d => {
        synth(196, 0.11, 0.13, d, "sawtooth", 1500, 650, 185);
        synth(207.65, 0.11, 0.11, d, "square", 1200, 500, 196);
      });
    },
    // Anime JoJo Bass-Drop / Dramatic Vine-Boom + clash impact!
    boom(){
      synth(150, 0.48, 0.24, 0, "sine", 900, 120, 34);
      synth(118, 0.36, 0.15, 0, "sawtooth", 1800, 180, 38);
      sweepNoise(0.28, 0.18, 0, 2600, 280, 1.1);
      bell(1396.9, 0.16, 0.06, 0, 420, "triangle"); // metallic clash transient
    },
    // Urgent anime countdown tick
    tick(){
      bell(1046.5, 0.045, 0.075, 0, 987.77, "sine");
      sweepNoise(0.02, 0.045, 0, 4000, 2400, 3);
    },
    // Joyful JRPG Level-Up / Anime Arcade Clear Fanfare!
    win(){
      const seq = [
        [523.25, 0.00, 0.13], [659.25, 0.09, 0.13], [783.99, 0.18, 0.13],
        [1046.5, 0.28, 0.36], [783.99, 0.28, 0.34], [1318.5, 0.37, 0.42], [1567.98, 0.45, 0.50]
      ];
      seq.forEach(([f, d, dur]) => bell(f, dur, 0.11, d, null, "triangle"));
      synth(261.63, 0.55, 0.08, 0.28, "sawtooth", 1800, 600);
      sweepNoise(0.28, 0.07, 0.28, 1800, 6800, 2.4);
    },
  };

  function confetti(opts={}){
    if(REDUCED()) return;
    const count = opts.count || 75;
    const colors = opts.colors || ["#FF3E78", "#00E0FF", "#FFC83D", "#00D4AA", "#B56BFF", "#FFFFFF"];
    const cvs = document.createElement("canvas");
    cvs.style.cssText = "position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:400";
    document.body.appendChild(cvs);
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const W = window.innerWidth, H = window.innerHeight;
    cvs.width = W * dpr; cvs.height = H * dpr;
    const c = cvs.getContext("2d"); c.scale(dpr, dpr);
    const ox = opts.x ?? W * 0.5, oy = opts.y ?? H * 0.38;
    const parts = Array.from({length: count}, () => {
      const a = Math.random() * Math.PI * 2;
      const sp = 3 + Math.random() * 11;
      return {
        x: ox, y: oy, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 5.5,
        w: 6 + Math.random() * 6, h: 4 + Math.random() * 4,
        rot: Math.random() * 6.28, vr: (Math.random() - 0.5) * 0.28,
        col: colors[Math.floor(Math.random() * colors.length)], life: 1,
      };
    });
    const tStart = performance.now();
    function frame(now){
      const dt = Math.min(0.05, (now - tStart) / 1000);
      c.clearRect(0, 0, W, H);
      let alive = 0;
      for(const p of parts){
        p.x += p.vx; p.y += p.vy; p.vy += 0.28; p.vx *= 0.985; p.rot += p.vr;
        p.life -= 0.011;
        if(p.life <= 0 || p.y > H + 30) continue;
        alive++;
        c.save(); c.translate(p.x, p.y); c.rotate(p.rot);
        c.globalAlpha = Math.max(0, Math.min(1, p.life * 1.4));
        c.fillStyle = p.col; c.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        c.restore();
      }
      if(alive > 0 && dt < 3.4) requestAnimationFrame(frame);
      else cvs.remove();
    }
    requestAnimationFrame(frame);
  }

  function shake(el=document.body, power=7){
    if(REDUCED() || !el) return;
    el.animate([
      {transform:"translate3d(0,0,0)"},
      {transform:`translate3d(${-power}px,${power*0.4}px,0)`},
      {transform:`translate3d(${power}px,${-power*0.4}px,0)`},
      {transform:`translate3d(${-power*0.6}px,${power*0.2}px,0)`},
      {transform:`translate3d(${power*0.4}px,0,0)`},
      {transform:"translate3d(0,0,0)"},
    ], {duration:340, easing:"cubic-bezier(.36,.07,.19,.97)"});
  }

  function burst(x, y, color="#FF3E78"){
    if(REDUCED()) return;
    const ring = document.createElement("div");
    ring.style.cssText = `position:fixed;left:${x}px;top:${y}px;width:24px;height:24px;margin:-12px 0 0 -12px;border-radius:50%;border:3px solid ${color};box-shadow:0 0 24px ${color};pointer-events:none;z-index:390`;
    document.body.appendChild(ring);
    ring.animate([
      {transform:"scale(.4)", opacity:1},
      {transform:"scale(5.5)", opacity:0},
    ], {duration:460, easing:"cubic-bezier(.16,1,.3,1)"}).onfinish = () => ring.remove();
  }

  function setMuted(m){
    muted = !!m;
    try{ localStorage.setItem("gn:muted", muted ? "1" : "0"); }catch(e){}
    document.querySelectorAll("[data-juice-mute]").forEach(b => {
      b.setAttribute("aria-pressed", String(muted));
      b.innerHTML = muted ? MUTE_OFF : MUTE_ON;
      b.title = muted ? "Unmute sound" : "Mute sound";
    });
  }
  const MUTE_ON = `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/></svg>`;
  const MUTE_OFF = `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>`;

  function mountMute(container){
    const host = container || document.querySelector("header.top, .bar .wrap");
    if(!host || host.querySelector("[data-juice-mute]") || host.querySelector("#soundBtn")) return;
    const b = document.createElement("button");
    b.type = "button"; b.className = "iconbtn"; b.dataset.juiceMute = "1";
    b.setAttribute("aria-pressed", String(muted));
    b.innerHTML = muted ? MUTE_OFF : MUTE_ON;
    b.title = muted ? "Unmute sound" : "Mute sound";
    b.setAttribute("aria-label", b.title);
    b.onclick = () => { setMuted(!muted); if(!muted) sfx.click(); };
    const before = host.querySelector(":scope > .timer");
    before ? host.insertBefore(b, before) : host.appendChild(b);
  }

  window.Juice = {sfx, confetti, shake, burst, muted: () => muted, setMuted, toggleMute: () => setMuted(!muted), mountMute};
})();
