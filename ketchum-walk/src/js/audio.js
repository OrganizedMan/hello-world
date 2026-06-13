/* Procedural ambience via WebAudio — wind, songbirds, the Big Wood River,
 * and crickets after dark. No audio files needed. */
KW.audio = (function () {
  const A = {};
  let ctx, master, windGain, riverGain, birdGain, cricketGain;
  let started = false;

  function noiseBuffer(seconds) {
    const sr = ctx.sampleRate;
    const buf = ctx.createBuffer(1, sr * seconds, sr);
    const d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return buf;
  }

  A.start = function () {
    if (started) return;
    started = true;
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain();
    master.gain.value = 0.7;
    master.connect(ctx.destination);

    const noise = noiseBuffer(4);

    // --- wind: lowpassed noise with slow swells ---
    {
      const src = ctx.createBufferSource();
      src.buffer = noise; src.loop = true;
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 380; lp.Q.value = 0.4;
      windGain = ctx.createGain(); windGain.gain.value = 0.05;
      src.connect(lp).connect(windGain).connect(master);
      src.start();
      const lfo = ctx.createOscillator();
      lfo.frequency.value = 0.07;
      const lfoG = ctx.createGain(); lfoG.gain.value = 0.028;
      lfo.connect(lfoG).connect(windGain.gain);
      lfo.start();
    }

    // --- river: bandpassed noise, volume set by distance each frame ---
    {
      const src = ctx.createBufferSource();
      src.buffer = noise; src.loop = true;
      src.playbackRate.value = 0.8;
      const bp = ctx.createBiquadFilter();
      bp.type = 'bandpass'; bp.frequency.value = 1200; bp.Q.value = 0.5;
      riverGain = ctx.createGain(); riverGain.gain.value = 0;
      src.connect(bp).connect(riverGain).connect(master);
      src.start();
    }

    birdGain = ctx.createGain(); birdGain.gain.value = 0.5; birdGain.connect(master);
    cricketGain = ctx.createGain(); cricketGain.gain.value = 0; cricketGain.connect(master);
    scheduleBird();
    startCrickets();
  };

  function chirp(t0, baseF) {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = 'sine';
    o.connect(g).connect(birdGain);
    const notes = 2 + Math.floor(Math.random() * 4);
    let t = t0;
    for (let i = 0; i < notes; i++) {
      const f = baseF * (0.9 + Math.random() * 0.4);
      o.frequency.setValueAtTime(f, t);
      o.frequency.exponentialRampToValueAtTime(f * (1.1 + Math.random() * 0.3), t + 0.06);
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.04 + Math.random() * 0.03, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
      t += 0.13 + Math.random() * 0.12;
    }
    o.start(t0); o.stop(t + 0.2);
  }

  function scheduleBird() {
    if (!started) return;
    const day = 1 - KW.env.nightT;
    if (day > 0.4 && Math.random() < 0.75) {
      chirp(ctx.currentTime + 0.05, 2200 + Math.random() * 1800);
    }
    setTimeout(scheduleBird, 1200 + Math.random() * 4500);
  }

  function startCrickets() {
    const o = ctx.createOscillator();
    o.type = 'triangle';
    o.frequency.value = 4400;
    const am = ctx.createOscillator();
    am.frequency.value = 14;
    const amG = ctx.createGain(); amG.gain.value = 0.5;
    const carrier = ctx.createGain(); carrier.gain.value = 0.012;
    am.connect(amG).connect(carrier.gain);
    o.connect(carrier).connect(cricketGain);
    o.start(); am.start();
  }

  A.update = function (playerPos) {
    if (!started) return;
    // river volume by distance to the Big Wood corridor
    const r = KW.env.riverPos;
    if (r) {
      const d = Math.hypot(playerPos.x - r.x, 0);
      const v = Math.max(0, 1 - d / 260) * 0.16;
      riverGain.gain.setTargetAtTime(v, ctx.currentTime, 0.5);
    }
    const night = KW.env.nightT;
    cricketGain.gain.setTargetAtTime(night * 0.65, ctx.currentTime, 0.8);
    birdGain.gain.setTargetAtTime((1 - night) * 0.5, ctx.currentTime, 0.8);
  };

  return A;
})();
