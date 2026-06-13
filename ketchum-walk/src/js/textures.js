/* Procedural canvas textures — no external assets, fully offline. */
KW.textures = (function () {
  function canvas(w, h) {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    return c;
  }
  function tex(c, repeat) {
    const t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.encoding = THREE.sRGBEncoding;
    t.anisotropy = 4;
    if (repeat) t.repeat.set(repeat[0], repeat[1]);
    return t;
  }
  function noise(ctx, w, h, alpha, n) {
    for (let i = 0; i < n; i++) {
      const v = Math.floor(Math.random() * 255);
      ctx.fillStyle = `rgba(${v},${v},${v},${alpha})`;
      ctx.fillRect(Math.random() * w, Math.random() * h, 1 + Math.random() * 2, 1 + Math.random() * 2);
    }
  }

  function grain() {
    // Subtle plaster/stucco grain — tinted by vertex colors on merged buildings.
    const c = canvas(256, 256), x = c.getContext('2d');
    x.fillStyle = '#e8e2d8'; x.fillRect(0, 0, 256, 256);
    noise(x, 256, 256, 0.05, 2600);
    return tex(c);
  }

  function brick(base, mortar) {
    const c = canvas(256, 256), x = c.getContext('2d');
    x.fillStyle = mortar; x.fillRect(0, 0, 256, 256);
    const bw = 32, bh = 12;
    for (let row = 0; row < 256 / bh; row++) {
      const off = (row % 2) * bw / 2;
      for (let col = -1; col < 256 / bw + 1; col++) {
        const shade = 0.86 + Math.random() * 0.24;
        const r = Math.min(255, Math.floor(base[0] * shade));
        const g = Math.min(255, Math.floor(base[1] * shade));
        const b = Math.min(255, Math.floor(base[2] * shade));
        x.fillStyle = `rgb(${r},${g},${b})`;
        x.fillRect(col * bw + off + 1, row * bh + 1, bw - 2, bh - 2);
      }
    }
    noise(x, 256, 256, 0.04, 1200);
    return tex(c);
  }

  function woodSiding(hex) {
    const c = canvas(256, 256), x = c.getContext('2d');
    x.fillStyle = hex; x.fillRect(0, 0, 256, 256);
    const board = 18;
    for (let yy = 0; yy < 256; yy += board) {
      x.fillStyle = 'rgba(0,0,0,0.22)'; x.fillRect(0, yy, 256, 2);
      x.fillStyle = 'rgba(255,255,255,0.06)'; x.fillRect(0, yy + 2, 256, 1);
      // wood streaks
      for (let i = 0; i < 8; i++) {
        x.fillStyle = `rgba(${Math.random() > 0.5 ? '60,38,20' : '255,235,200'},0.05)`;
        x.fillRect(Math.random() * 256, yy + 3, 30 + Math.random() * 80, 2 + Math.random() * 4);
      }
    }
    return tex(c);
  }

  function stone() {
    const c = canvas(256, 256), x = c.getContext('2d');
    x.fillStyle = '#7d7468'; x.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 110; i++) {
      const w = 18 + Math.random() * 40, h = 12 + Math.random() * 22;
      const px = Math.random() * 256, py = Math.random() * 256;
      const v = 105 + Math.random() * 70;
      x.fillStyle = `rgb(${v + 8},${v},${v - 10})`;
      x.beginPath();
      x.ellipse(px, py, w / 2, h / 2, Math.random(), 0, Math.PI * 2);
      x.fill();
      x.strokeStyle = 'rgba(40,35,28,0.5)'; x.lineWidth = 2; x.stroke();
    }
    noise(x, 256, 256, 0.05, 1500);
    return tex(c);
  }

  function asphalt() {
    const c = canvas(256, 256), x = c.getContext('2d');
    x.fillStyle = '#3c3c40'; x.fillRect(0, 0, 256, 256);
    noise(x, 256, 256, 0.07, 3200);
    for (let i = 0; i < 26; i++) { // cracks/patches
      x.fillStyle = 'rgba(0,0,0,0.18)';
      x.fillRect(Math.random() * 256, Math.random() * 256, 2 + Math.random() * 30, 1 + Math.random() * 3);
    }
    return tex(c);
  }

  function concrete() {
    const c = canvas(256, 256), x = c.getContext('2d');
    x.fillStyle = '#9b968c'; x.fillRect(0, 0, 256, 256);
    noise(x, 256, 256, 0.05, 2200);
    // expansion joints
    x.strokeStyle = 'rgba(0,0,0,0.28)'; x.lineWidth = 3;
    x.beginPath();
    x.moveTo(0, 128); x.lineTo(256, 128);
    x.moveTo(128, 0); x.lineTo(128, 256);
    x.stroke();
    return tex(c);
  }

  function grass() {
    const c = canvas(256, 256), x = c.getContext('2d');
    x.fillStyle = '#6d7c3f'; x.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 4200; i++) {
      const g = 95 + Math.random() * 70;
      x.fillStyle = `rgba(${g * 0.78},${g},${g * 0.38},0.5)`;
      x.fillRect(Math.random() * 256, Math.random() * 256, 1, 2 + Math.random() * 2);
    }
    return tex(c);
  }

  function awning(colA, colB) {
    const c = canvas(128, 64), x = c.getContext('2d');
    for (let i = 0; i < 8; i++) {
      x.fillStyle = i % 2 ? colA : colB;
      x.fillRect(i * 16, 0, 16, 64);
    }
    return tex(c);
  }

  /**
   * Sign plate texture. style: 'wood' | 'paint' | 'neon'
   */
  function sign(text, style, sub) {
    const c = canvas(512, 128), x = c.getContext('2d');
    if (style === 'wood') {
      x.fillStyle = '#503a22'; x.fillRect(0, 0, 512, 128);
      for (let i = 0; i < 60; i++) {
        x.fillStyle = 'rgba(30,18,8,0.25)';
        x.fillRect(0, Math.random() * 128, 512, 1);
      }
      x.strokeStyle = '#2c2012'; x.lineWidth = 10; x.strokeRect(5, 5, 502, 118);
      x.fillStyle = '#f2dfae';
    } else if (style === 'neon') {
      x.fillStyle = '#181818'; x.fillRect(0, 0, 512, 128);
      x.strokeStyle = '#101010'; x.lineWidth = 8; x.strokeRect(4, 4, 504, 120);
      x.shadowColor = '#ff5a3c'; x.shadowBlur = 22;
      x.fillStyle = '#ffd9c2';
    } else {
      x.fillStyle = '#27313a'; x.fillRect(0, 0, 512, 128);
      x.strokeStyle = '#cfa75c'; x.lineWidth = 6; x.strokeRect(8, 8, 496, 112);
      x.fillStyle = '#efe3c8';
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

  // Bald Mountain face: forest green with pale ski-run swaths converging at the top.
  function baldy() {
    const c = canvas(1024, 512), x = c.getContext('2d');
    const grd = x.createLinearGradient(0, 0, 0, 512);
    grd.addColorStop(0, '#5a6147');
    grd.addColorStop(0.55, '#3f5535');
    grd.addColorStop(1, '#37492f');
    x.fillStyle = grd; x.fillRect(0, 0, 1024, 512);
    // tree speckle
    for (let i = 0; i < 9000; i++) {
      const py = Math.random() * 512;
      const g = 50 + Math.random() * 45 * (py / 512 + 0.4);
      x.fillStyle = `rgba(${g * 0.55},${g},${g * 0.5},0.6)`;
      x.fillRect(Math.random() * 1024, py, 2, 3);
    }
    // ski runs fanning down from summit area
    const summitX = 560;
    for (let i = 0; i < 9; i++) {
      const endX = 120 + i * 100 + Math.random() * 50;
      x.strokeStyle = 'rgba(168,178,128,0.85)';
      x.lineWidth = 14 + Math.random() * 16;
      x.beginPath();
      x.moveTo(summitX + (Math.random() * 60 - 30), 30);
      x.bezierCurveTo(summitX + (endX - summitX) * 0.3, 170,
        summitX + (endX - summitX) * 0.7, 330, endX, 512);
      x.stroke();
    }
    const t = tex(c);
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    return t;
  }

  function ridge() {
    // Distant sage/forest hillsides.
    const c = canvas(512, 256), x = c.getContext('2d');
    const grd = x.createLinearGradient(0, 0, 0, 256);
    grd.addColorStop(0, '#59604a');
    grd.addColorStop(1, '#3c4a36');
    x.fillStyle = grd; x.fillRect(0, 0, 512, 256);
    for (let i = 0; i < 5000; i++) {
      const py = Math.random() * 256;
      const g = 60 + Math.random() * 50;
      x.fillStyle = `rgba(${g * 0.85},${g},${g * 0.6},0.45)`;
      x.fillRect(Math.random() * 512, py, 2, 2);
    }
    return tex(c, [3, 1]);
  }

  return {
    grain, brick, woodSiding, stone, asphalt, concrete, grass,
    awning, sign, streetName, baldy, ridge,
  };
})();
