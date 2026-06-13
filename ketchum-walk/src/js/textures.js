/* Procedural canvas textures — no external assets, fully offline.
 * v2: 512px materials with bump relief for every surface. */
KW.textures = (function () {
  function canvas(w, h) {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    return c;
  }
  function tex(c, repeat, linear) {
    const t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    if (!linear) {
      // sRGB tagging across three versions (encoding API removed in r152+)
      if ('colorSpace' in t) t.colorSpace = THREE.SRGBColorSpace || 'srgb';
      else t.encoding = THREE.sRGBEncoding;
    }
    t.anisotropy = 8;
    if (repeat) t.repeat.set(repeat[0], repeat[1]);
    return t;
  }
  function noise(x, w, h, alpha, n, sizeMax) {
    for (let i = 0; i < n; i++) {
      const v = Math.floor(Math.random() * 255);
      x.fillStyle = `rgba(${v},${v},${v},${alpha})`;
      x.fillRect(Math.random() * w, Math.random() * h, 1 + Math.random() * (sizeMax || 2), 1 + Math.random() * (sizeMax || 2));
    }
  }
  function shade(hex, f) {
    const r = (hex >> 16) & 255, g = (hex >> 8) & 255, b = hex & 255;
    return `rgb(${Math.min(255, r * f) | 0},${Math.min(255, g * f) | 0},${Math.min(255, b * f) | 0})`;
  }

  /** Returns { map, bumpMap } pairs. The bump canvas is grayscale relief. */
  function withBump(colorCanvas, bumpCanvas, repeat) {
    return { map: tex(colorCanvas, repeat), bumpMap: tex(bumpCanvas, repeat, true) };
  }

  // ---------- facades ----------

  function brick(base, mortarHex, weathering) {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = shade(mortarHex, 1); x.fillRect(0, 0, S, S);
    bx.fillStyle = '#404040'; bx.fillRect(0, 0, S, S);
    const bw = 64, bh = 26;
    for (let row = 0; row < S / bh; row++) {
      const off = (row % 2) * bw / 2;
      for (let col = -1; col < S / bw + 1; col++) {
        const f = 0.78 + Math.random() * 0.42;
        x.fillStyle = shade(base, f);
        const px = col * bw + off + 2, py = row * bh + 2;
        x.fillRect(px, py, bw - 4, bh - 4);
        // per-brick mottling
        for (let i = 0; i < 5; i++) {
          x.fillStyle = `rgba(${Math.random() < 0.5 ? '0,0,0' : '255,240,220'},${0.05 + Math.random() * 0.06})`;
          x.fillRect(px + Math.random() * (bw - 10), py + Math.random() * (bh - 8), 4 + Math.random() * 14, 3 + Math.random() * 6);
        }
        bx.fillStyle = `rgb(${150 + f * 40 | 0},${150 + f * 40 | 0},${150 + f * 40 | 0})`;
        bx.fillRect(px, py, bw - 4, bh - 4);
      }
    }
    if (weathering) { // grime streaks from ledges
      for (let i = 0; i < 24; i++) {
        const gx = Math.random() * S, gy = Math.random() * S;
        const grd = x.createLinearGradient(0, gy, 0, gy + 60);
        grd.addColorStop(0, 'rgba(30,24,18,0.18)'); grd.addColorStop(1, 'rgba(30,24,18,0)');
        x.fillStyle = grd; x.fillRect(gx, gy, 8 + Math.random() * 22, 60);
      }
    }
    noise(x, S, S, 0.04, 4000);
    return withBump(c, b);
  }

  function clapboard(baseHex) {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    const board = 34;
    for (let yy = 0; yy < S; yy += board) {
      const f = 0.92 + Math.random() * 0.16;
      x.fillStyle = shade(baseHex, f); x.fillRect(0, yy, S, board);
      const grd = bx.createLinearGradient(0, yy, 0, yy + board);
      grd.addColorStop(0, '#b0b0b0'); grd.addColorStop(0.85, '#6a6a6a'); grd.addColorStop(1, '#202020');
      bx.fillStyle = grd; bx.fillRect(0, yy, S, board);
      // shadow line under each board + wood streaks
      x.fillStyle = 'rgba(0,0,0,0.30)'; x.fillRect(0, yy + board - 3, S, 3);
      x.fillStyle = 'rgba(255,255,255,0.07)'; x.fillRect(0, yy, S, 2);
      for (let i = 0; i < 14; i++) {
        x.fillStyle = `rgba(${Math.random() < 0.5 ? '50,32,16' : '255,240,210'},0.06)`;
        x.fillRect(Math.random() * S, yy + 4 + Math.random() * (board - 10), 40 + Math.random() * 140, 2);
      }
      // board joints
      for (let i = 0; i < 3; i++) {
        const jx = Math.random() * S;
        x.fillStyle = 'rgba(0,0,0,0.2)'; x.fillRect(jx, yy, 2, board);
      }
    }
    noise(x, S, S, 0.03, 2500);
    return withBump(c, b);
  }

  function boardBatten(baseHex) {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = shade(baseHex, 1); x.fillRect(0, 0, S, S);
    bx.fillStyle = '#707070'; bx.fillRect(0, 0, S, S);
    for (let i = 0; i < 40; i++) { // vertical grain
      x.fillStyle = `rgba(${Math.random() < 0.5 ? '40,26,12' : '255,238,205'},0.07)`;
      x.fillRect(Math.random() * S, 0, 2 + Math.random() * 3, S);
    }
    const bat = 86;
    for (let xx = 0; xx < S; xx += bat) {
      x.fillStyle = shade(baseHex, 0.82); x.fillRect(xx, 0, 12, S);
      x.fillStyle = 'rgba(255,255,255,0.10)'; x.fillRect(xx, 0, 3, S);
      x.fillStyle = 'rgba(0,0,0,0.25)'; x.fillRect(xx + 12, 0, 3, S);
      bx.fillStyle = '#e8e8e8'; bx.fillRect(xx, 0, 12, S);
    }
    noise(x, S, S, 0.035, 2500);
    return withBump(c, b);
  }

  function stucco(baseHex) {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = shade(baseHex, 1); x.fillRect(0, 0, S, S);
    bx.fillStyle = '#808080'; bx.fillRect(0, 0, S, S);
    for (let i = 0; i < 9000; i++) {
      const v = Math.random();
      x.fillStyle = `rgba(${v < 0.5 ? '0,0,0' : '255,250,240'},${0.03 + Math.random() * 0.05})`;
      const px = Math.random() * S, py = Math.random() * S, s = 1 + Math.random() * 3;
      x.fillRect(px, py, s, s);
      bx.fillStyle = `rgba(${v < 0.5 ? '40,40,40' : '220,220,220'},0.25)`;
      bx.fillRect(px, py, s, s);
    }
    // faint trowel arcs
    for (let i = 0; i < 30; i++) {
      x.strokeStyle = 'rgba(0,0,0,0.04)'; x.lineWidth = 6;
      x.beginPath();
      x.arc(Math.random() * S, Math.random() * S, 30 + Math.random() * 60, 0, 2 + Math.random() * 2);
      x.stroke();
    }
    return withBump(c, b);
  }

  function stone() {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = '#5e574c'; x.fillRect(0, 0, S, S);
    bx.fillStyle = '#303030'; bx.fillRect(0, 0, S, S);
    for (let i = 0; i < 240; i++) {
      const w = 30 + Math.random() * 70, h = 20 + Math.random() * 36;
      const px = Math.random() * S, py = Math.random() * S;
      const v = 110 + Math.random() * 80;
      x.fillStyle = `rgb(${v + 12 | 0},${v | 0},${v - 14 | 0})`;
      x.beginPath();
      x.ellipse(px, py, w / 2, h / 2, Math.random() * 0.6 - 0.3, 0, Math.PI * 2);
      x.fill();
      x.strokeStyle = 'rgba(30,26,20,0.6)'; x.lineWidth = 3; x.stroke();
      bx.fillStyle = `rgb(${90 + v / 2 | 0},${90 + v / 2 | 0},${90 + v / 2 | 0})`;
      bx.beginPath();
      bx.ellipse(px, py, w / 2 - 2, h / 2 - 2, 0, 0, Math.PI * 2);
      bx.fill();
    }
    noise(x, S, S, 0.05, 3000);
    return withBump(c, b);
  }

  function logWall() {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    const lh = 52;
    for (let yy = 0; yy < S; yy += lh) {
      const f = 0.85 + Math.random() * 0.25;
      const grd = x.createLinearGradient(0, yy, 0, yy + lh);
      grd.addColorStop(0, shade(0x8a6a44, f * 1.15));
      grd.addColorStop(0.5, shade(0x8a6a44, f));
      grd.addColorStop(1, shade(0x5c4226, f));
      x.fillStyle = grd; x.fillRect(0, yy, S, lh);
      const bg = bx.createLinearGradient(0, yy, 0, yy + lh);
      bg.addColorStop(0, '#c8c8c8'); bg.addColorStop(0.5, '#909090'); bg.addColorStop(1, '#181818');
      bx.fillStyle = bg; bx.fillRect(0, yy, S, lh);
      for (let i = 0; i < 26; i++) {
        x.fillStyle = `rgba(40,24,10,${0.05 + Math.random() * 0.08})`;
        x.fillRect(Math.random() * S, yy + 4 + Math.random() * (lh - 8), 60 + Math.random() * 180, 2);
      }
      x.fillStyle = 'rgba(20,12,5,0.5)'; x.fillRect(0, yy + lh - 4, S, 4); // chinking shadow
    }
    return withBump(c, b);
  }

  // ---------- roofs ----------

  function shingles(baseHex) {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = shade(baseHex, 0.8); x.fillRect(0, 0, S, S);
    bx.fillStyle = '#606060'; bx.fillRect(0, 0, S, S);
    const sh = 30, sw = 52;
    for (let row = 0; row < S / sh; row++) {
      const off = (row % 2) * sw / 2;
      for (let col = -1; col < S / sw + 1; col++) {
        x.fillStyle = shade(baseHex, 0.75 + Math.random() * 0.45);
        x.fillRect(col * sw + off + 1, row * sh, sw - 2, sh - 3);
      }
      x.fillStyle = 'rgba(0,0,0,0.35)'; x.fillRect(0, row * sh + sh - 3, S, 3);
      bx.fillStyle = '#161616'; bx.fillRect(0, row * sh + sh - 3, S, 3);
    }
    noise(x, S, S, 0.05, 3000);
    return withBump(c, b);
  }

  function metalRoof(baseHex) {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = shade(baseHex, 1); x.fillRect(0, 0, S, S);
    bx.fillStyle = '#787878'; bx.fillRect(0, 0, S, S);
    for (let xx = 0; xx < S; xx += 64) {
      const grd = x.createLinearGradient(xx, 0, xx + 64, 0);
      grd.addColorStop(0, 'rgba(255,255,255,0.12)');
      grd.addColorStop(0.5, 'rgba(0,0,0,0.06)');
      grd.addColorStop(1, 'rgba(0,0,0,0.16)');
      x.fillStyle = grd; x.fillRect(xx, 0, 64, S);
      x.fillStyle = 'rgba(255,255,255,0.25)'; x.fillRect(xx, 0, 4, S);
      bx.fillStyle = '#ffffff'; bx.fillRect(xx, 0, 5, S);
    }
    noise(x, S, S, 0.025, 1200);
    return withBump(c, b);
  }

  // ---------- ground ----------

  function asphalt() {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = '#36363a'; x.fillRect(0, 0, S, S);
    bx.fillStyle = '#808080'; bx.fillRect(0, 0, S, S);
    noise(x, S, S, 0.07, 9000, 3);
    noise(bx, S, S, 0.35, 5000, 2);
    for (let i = 0; i < 50; i++) { // patches & cracks
      x.fillStyle = `rgba(${Math.random() < 0.6 ? '0,0,0' : '90,88,84'},0.16)`;
      const w = 8 + Math.random() * 90;
      x.fillRect(Math.random() * S, Math.random() * S, w, 2 + Math.random() * 5);
    }
    for (let i = 0; i < 8; i++) { // tar snakes
      x.strokeStyle = 'rgba(12,12,14,0.7)'; x.lineWidth = 3;
      x.beginPath();
      let px = Math.random() * S, py = Math.random() * S;
      x.moveTo(px, py);
      for (let j = 0; j < 5; j++) { px += (Math.random() - 0.5) * 120; py += Math.random() * 60; x.lineTo(px, py); }
      x.stroke();
    }
    return withBump(c, b);
  }

  function concrete() {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = '#a09a8e'; x.fillRect(0, 0, S, S);
    bx.fillStyle = '#909090'; bx.fillRect(0, 0, S, S);
    noise(x, S, S, 0.05, 7000, 2);
    for (let i = 0; i < 40; i++) {
      x.fillStyle = 'rgba(60,52,40,0.10)';
      x.fillRect(Math.random() * S, Math.random() * S, 20 + Math.random() * 60, 14 + Math.random() * 40);
    }
    x.strokeStyle = 'rgba(20,16,12,0.45)'; x.lineWidth = 4;
    x.beginPath(); x.moveTo(0, 256); x.lineTo(S, 256); x.moveTo(256, 0); x.lineTo(256, S); x.stroke();
    bx.strokeStyle = '#101010'; bx.lineWidth = 4;
    bx.beginPath(); bx.moveTo(0, 256); bx.lineTo(S, 256); bx.moveTo(256, 0); bx.lineTo(256, S); bx.stroke();
    return withBump(c, b);
  }

  function gravel() {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    x.fillStyle = '#8d8378'; x.fillRect(0, 0, S, S);
    bx.fillStyle = '#707070'; bx.fillRect(0, 0, S, S);
    for (let i = 0; i < 14000; i++) {
      const v = 90 + Math.random() * 110;
      x.fillStyle = `rgb(${v + 8 | 0},${v | 0},${v - 12 | 0})`;
      const px = Math.random() * S, py = Math.random() * S, s = 1 + Math.random() * 3;
      x.fillRect(px, py, s, s);
      bx.fillStyle = `rgb(${v | 0},${v | 0},${v | 0})`; bx.fillRect(px, py, s, s);
    }
    return withBump(c, b);
  }

  function grass() {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    x.fillStyle = '#67753f'; x.fillRect(0, 0, S, S);
    for (let i = 0; i < 18000; i++) {
      const g = 90 + Math.random() * 80;
      x.fillStyle = `rgba(${g * 0.72 | 0},${g | 0},${g * 0.38 | 0},0.55)`;
      x.fillRect(Math.random() * S, Math.random() * S, 1, 2 + Math.random() * 3);
    }
    for (let i = 0; i < 40; i++) { // dry patches
      x.fillStyle = 'rgba(150,135,80,0.10)';
      x.beginPath(); x.arc(Math.random() * S, Math.random() * S, 10 + Math.random() * 30, 0, 7); x.fill();
    }
    return { map: tex(c) };
  }

  // terrain detail overlay (tinted by vertex colors)
  function terrainDetail() {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    x.fillStyle = '#9a9a92'; x.fillRect(0, 0, S, S);
    noise(x, S, S, 0.10, 14000, 3);
    for (let i = 0; i < 700; i++) { // scrub clumps
      x.fillStyle = `rgba(${40 + Math.random() * 40 | 0},${55 + Math.random() * 45 | 0},${30 | 0},0.30)`;
      x.beginPath(); x.arc(Math.random() * S, Math.random() * S, 2 + Math.random() * 5, 0, 7); x.fill();
    }
    return { map: tex(c) };
  }

  function water() {
    const S = 256, c = canvas(S, S), x = c.getContext('2d');
    x.fillStyle = '#3d6079'; x.fillRect(0, 0, S, S);
    for (let i = 0; i < 600; i++) {
      x.fillStyle = `rgba(${Math.random() < 0.5 ? '255,255,255' : '20,40,60'},${0.05 + Math.random() * 0.08})`;
      x.fillRect(Math.random() * S, Math.random() * S, 6 + Math.random() * 30, 1 + Math.random());
    }
    return { map: tex(c) };
  }

  // ---------- interior ----------

  function woodFloor() {
    const S = 512, c = canvas(S, S), x = c.getContext('2d');
    const b = canvas(S, S), bx = b.getContext('2d');
    bx.fillStyle = '#808080'; bx.fillRect(0, 0, S, S);
    const pw = 64;
    for (let xx = 0; xx < S; xx += pw) {
      let yy = -Math.random() * 100;
      while (yy < S) {
        const len = 140 + Math.random() * 160;
        const f = 0.8 + Math.random() * 0.4;
        const grd = x.createLinearGradient(xx, 0, xx + pw, 0);
        grd.addColorStop(0, shade(0x7a5530, f * 1.08));
        grd.addColorStop(1, shade(0x7a5530, f * 0.92));
        x.fillStyle = grd; x.fillRect(xx, yy, pw - 2, len - 2);
        for (let i = 0; i < 16; i++) {
          x.fillStyle = `rgba(40,22,8,${0.05 + Math.random() * 0.07})`;
          x.fillRect(xx + 4 + Math.random() * (pw - 12), yy + Math.random() * len, 2, 20 + Math.random() * 60);
        }
        bx.fillStyle = '#202020'; bx.fillRect(xx, yy + len - 2, pw, 2);
        yy += len;
      }
      x.fillStyle = 'rgba(10,6,2,0.5)'; x.fillRect(xx + pw - 2, 0, 2, S);
      bx.fillStyle = '#181818'; bx.fillRect(xx + pw - 2, 0, 2, S);
    }
    noise(x, S, S, 0.03, 2000);
    return withBump(c, b);
  }

  function barTop() {
    const S = 512, c = canvas(S, 128), x = c.getContext('2d');
    const grd = x.createLinearGradient(0, 0, 0, 128);
    grd.addColorStop(0, '#5e3c1c'); grd.addColorStop(0.5, '#4a2e14'); grd.addColorStop(1, '#3a2410');
    x.fillStyle = grd; x.fillRect(0, 0, S, 128);
    for (let i = 0; i < 80; i++) {
      x.fillStyle = `rgba(${Math.random() < 0.5 ? '20,10,4' : '200,150,90'},0.08)`;
      x.fillRect(Math.random() * S, Math.random() * 128, 80 + Math.random() * 200, 1 + Math.random() * 2);
    }
    // glass rings
    for (let i = 0; i < 10; i++) {
      x.strokeStyle = 'rgba(230,210,170,0.10)'; x.lineWidth = 2;
      x.beginPath(); x.arc(Math.random() * S, Math.random() * 128, 8 + Math.random() * 6, 0, 7); x.stroke();
    }
    return { map: tex(c) };
  }

  // ---------- signage ----------

  function sign(text, style, sub) {
    const c = canvas(512, 128), x = c.getContext('2d');
    if (style === 'wood') {
      x.fillStyle = '#503a22'; x.fillRect(0, 0, 512, 128);
      for (let i = 0; i < 70; i++) {
        x.fillStyle = 'rgba(30,18,8,0.25)';
        x.fillRect(0, Math.random() * 128, 512, 1);
      }
      x.strokeStyle = '#2c2012'; x.lineWidth = 10; x.strokeRect(5, 5, 502, 118);
      x.fillStyle = '#f2dfae';
    } else if (style === 'neon') {
      x.fillStyle = '#141414'; x.fillRect(0, 0, 512, 128);
      x.strokeStyle = '#0c0c0c'; x.lineWidth = 8; x.strokeRect(4, 4, 504, 120);
      x.shadowColor = '#ff5a3c'; x.shadowBlur = 26;
      x.fillStyle = '#ffe2cc';
    } else {
      const bgs = ['#27313a', '#3a2c22', '#243528', '#3a2430', '#2c2c34'];
      x.fillStyle = bgs[(text.length * 7) % bgs.length]; x.fillRect(0, 0, 512, 128);
      x.strokeStyle = '#cfa75c'; x.lineWidth = 6; x.strokeRect(8, 8, 496, 112);
      x.fillStyle = '#efe3c8';
      noise(x, 512, 128, 0.03, 600);
    }
    x.textAlign = 'center'; x.textBaseline = 'middle';
    let size = 64;
    x.font = `bold ${size}px Georgia, serif`;
    while (x.measureText(text).width > 460 && size > 22) {
      size -= 4; x.font = `bold ${size}px Georgia, serif`;
    }
    x.fillText(text, 256, sub ? 52 : 64);
    if (sub) {
      x.shadowBlur = 0;
      x.font = 'italic 26px Georgia, serif';
      x.fillStyle = 'rgba(240,225,190,0.85)';
      x.fillText(sub, 256, 100);
    }
    const t = tex(c);
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    return t;
  }

  function streetName(text) {
    const c = canvas(256, 64), x = c.getContext('2d');
    x.fillStyle = '#1d5c3a'; x.fillRect(0, 0, 256, 64);
    x.strokeStyle = '#ffffff'; x.lineWidth = 4; x.strokeRect(3, 3, 250, 58);
    x.fillStyle = '#ffffff'; x.textAlign = 'center'; x.textBaseline = 'middle';
    let size = 34;
    x.font = `bold ${size}px Helvetica, Arial, sans-serif`;
    while (x.measureText(text).width > 230 && size > 14) {
      size -= 2; x.font = `bold ${size}px Helvetica, Arial, sans-serif`;
    }
    x.fillText(text, 128, 34);
    const t = tex(c);
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    return t;
  }

  function stopSign() {
    const c = canvas(128, 128), x = c.getContext('2d');
    x.fillStyle = '#b32820';
    x.beginPath();
    for (let i = 0; i < 8; i++) {
      const a = Math.PI / 8 + i * Math.PI / 4;
      x[i ? 'lineTo' : 'moveTo'](64 + 60 * Math.cos(a), 64 + 60 * Math.sin(a));
    }
    x.closePath(); x.fill();
    x.strokeStyle = '#ffffff'; x.lineWidth = 5; x.stroke();
    x.fillStyle = '#ffffff'; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.font = 'bold 40px Helvetica, Arial, sans-serif';
    x.fillText('STOP', 64, 66);
    const t = tex(c);
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    return t;
  }

  function awningStripes(colA, colB) {
    const c = canvas(256, 128), x = c.getContext('2d');
    for (let i = 0; i < 8; i++) {
      x.fillStyle = i % 2 ? colA : colB;
      x.fillRect(i * 32, 0, 32, 128);
    }
    const grd = x.createLinearGradient(0, 0, 0, 128);
    grd.addColorStop(0, 'rgba(255,255,255,0.10)'); grd.addColorStop(1, 'rgba(0,0,0,0.22)');
    x.fillStyle = grd; x.fillRect(0, 0, 256, 128);
    return { map: tex(c) };
  }

  function tvScreen() {
    const c = canvas(256, 144), x = c.getContext('2d');
    x.fillStyle = '#1a3a18'; x.fillRect(0, 0, 256, 144); // ballgame green
    x.fillStyle = '#2c5828'; x.fillRect(20, 30, 216, 90);
    x.fillStyle = 'rgba(255,255,255,0.85)';
    for (let i = 0; i < 14; i++) x.fillRect(30 + Math.random() * 196, 40 + Math.random() * 70, 3, 6);
    x.fillStyle = '#101418'; x.fillRect(0, 0, 256, 22);
    x.fillStyle = '#e8e2cc'; x.font = 'bold 13px Helvetica'; x.textAlign = 'left';
    x.fillText('TOP 9   SEA 3 — BOS 2', 12, 15);
    const t = tex(c);
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    return t;
  }

  return {
    brick, clapboard, boardBatten, stucco, stone, logWall,
    shingles, metalRoof,
    asphalt, concrete, gravel, grass, terrainDetail, water,
    woodFloor, barTop,
    sign, streetName, stopSign, awningStripes, tvScreen,
  };
})();
