/* Data-driven building generator v2.
 * Every facade gets a real material (brick / clapboard / board-and-batten /
 * stucco / stone / log) with bump relief; windows get frames, sills and
 * mullions; storefronts get bulkheads, recessed doors, transoms and
 * cornices with dentils. Geometry is merged per-material to keep draw
 * calls low (~20 meshes for the whole town). */
KW.buildings = (function () {
  const B = {};

  // ---- shared material/batch registry ----
  let R = null;
  function registry() {
    if (R) return R;
    const T = KW.textures;
    R = { batches: {}, mats: {}, order: [] };

    function phong(key, texPair, opts) {
      const m = new THREE.MeshPhongMaterial(Object.assign({
        map: texPair.map, bumpMap: texPair.bumpMap, bumpScale: 0.035,
        shininess: 4, specular: 0x222222,
      }, opts || {}));
      R.mats[key] = m; R.order.push(key);
    }

    phong('brick_red', T.brick(0x9E4A33, 0xB8AfA0, true));
    phong('brick_tan', T.brick(0xB78A5E, 0xC2B8A8, true));
    phong('brick_paint', T.brick(0xD8CFBA, 0xCCC4B2, false));
    phong('clap_cream', T.clapboard(0xD9CDB0));
    phong('clap_sage', T.clapboard(0x9BA888));
    phong('clap_blue', T.clapboard(0x7E93A0));
    phong('clap_red', T.clapboard(0x9E5240));
    phong('clap_brown', T.clapboard(0x7A5C3E));
    phong('batten_tan', T.boardBatten(0xB09468));
    phong('batten_grey', T.boardBatten(0x848A84));
    phong('batten_dark', T.boardBatten(0x5C4A38));
    phong('stucco_cream', T.stucco(0xDDD3BC));
    phong('stucco_rose', T.stucco(0xC9A386));
    phong('stucco_grey', T.stucco(0xB4B4AA));
    phong('stone', T.stone(), { bumpScale: 0.06 });
    phong('log', T.logWall(), { bumpScale: 0.06 });
    phong('roof_shingle', T.shingles(0x57534E));
    phong('roof_metal_green', T.metalRoof(0x44584A));
    phong('roof_metal_red', T.metalRoof(0x6E3B30));
    phong('roof_metal_grey', T.metalRoof(0x70747A));

    // painted wood trim — vertex-colored
    R.mats.trim = new THREE.MeshLambertMaterial({ vertexColors: true });
    R.order.push('trim');

    R.mats.glassLit = new THREE.MeshPhongMaterial({
      color: 0x2E3D48, emissive: 0xFFC97A, emissiveIntensity: 0,
      shininess: 90, specular: 0x99AABB,
    });
    R.mats.glassLit.userData = { dayGlow: 0, nightGlow: 1.4 };
    KW.env.emissiveMats.push(R.mats.glassLit);
    R.order.push('glassLit');
    R.mats.glassDark = new THREE.MeshPhongMaterial({
      color: 0x1C262E, shininess: 95, specular: 0xAABBCC,
    });
    R.order.push('glassDark');

    const aw1 = T.awningStripes('#6E2F28', '#D9CDB2');
    const aw2 = T.awningStripes('#35424A', '#C8C2B0');
    const aw3 = T.awningStripes('#3F5238', '#3F5238'); // solid
    phong('awning_red', aw1, { bumpMap: null, shininess: 10 });
    phong('awning_blue', aw2, { bumpMap: null, shininess: 10 });
    phong('awning_green', aw3, { bumpMap: null, shininess: 10 });

    for (const k of R.order) R.batches[k] = new KW.util.GeoBatch();
    return R;
  }

  const FACADES = {
    falsefront: ['clap_cream', 'clap_sage', 'clap_blue', 'clap_red', 'clap_brown', 'batten_tan', 'batten_dark'],
    brick: ['brick_red', 'brick_tan', 'brick_paint'],
    retail: ['stucco_cream', 'stucco_rose', 'stucco_grey', 'brick_paint', 'batten_grey'],
    chalet: ['clap_brown', 'batten_tan', 'batten_dark', 'log', 'clap_sage'],
    lodge: ['batten_tan', 'stone'],
  };
  const TRIM_COLORS = [0xF2EAD8, 0x3A3328, 0x5C4A36, 0x2E3A40, 0x6E5136, 0xE8E0CC];
  const AWNINGS = ['awning_red', 'awning_blue', 'awning_green'];

  B.generate = function (specs, scene, colliders) {
    const reg = registry();
    const signs = [];
    const r = KW.util.rng(1337);

    for (const s of specs) {
      buildOne(s, reg, signs, r);
      if (!s.noCollide) colliders.push(footprint(s));
    }
    B.flush(scene, signs);
  };

  /** Emit merged meshes for everything accumulated since the last flush. */
  B.flush = function (scene, signs) {
    const reg = registry();
    for (const k of reg.order) {
      const g = reg.batches[k].merge();
      if (!g) continue;
      const mesh = new THREE.Mesh(g, reg.mats[k]);
      if (k !== 'glassLit' && k !== 'glassDark') {
        mesh.castShadow = true; mesh.receiveShadow = true;
      }
      scene.add(mesh);
    }
    if (signs) for (const m of signs) scene.add(m);
  };
  B.registry = registry;

  function footprint(s) {
    const hw = s.w / 2 + 0.05, hd = s.d / 2 + 0.05;
    const cos = Math.abs(Math.cos(s.ry || 0)), sin = Math.abs(Math.sin(s.ry || 0));
    const ex = hw * cos + hd * sin, ez = hw * sin + hd * cos;
    return { minX: s.x - ex, maxX: s.x + ex, minZ: s.z - ez, maxZ: s.z + ez };
  }

  function mat4(s, lx, ly, lz) {
    const m = new THREE.Matrix4().makeRotationY(s.ry || 0);
    const v = new THREE.Vector3(lx, ly, lz).applyMatrix4(new THREE.Matrix4().makeRotationY(s.ry || 0));
    m.setPosition(s.x + v.x, ly, s.z + v.z);
    return m;
  }
  function lbox(batch, s, w, h, d, lx, ly, lz, colorOrUv) {
    const g = new THREE.BoxGeometry(w, h, d);
    const uv = typeof colorOrUv === 'number' || colorOrUv instanceof THREE.Color ? null : colorOrUv;
    batch.add(g, mat4(s, lx, ly, lz),
      uv ? 0xFFFFFF : colorOrUv,
      [Math.max(w, d) * 0.32, h * 0.32]);
  }

  function buildOne(s, reg, signs, r) {
    const pick = KW.util.pick;
    const floors = s.floors || 1;
    const fh = s.floorH || 3.4;
    const h = s.h || floors * fh + 0.6;
    const front = s.d / 2;
    const facadeKey = s.facade || pick(r, FACADES[s.style] || FACADES.retail);
    const trimC = new THREE.Color(s.trim !== undefined ? s.trim : pick(r, TRIM_COLORS));
    const FB = reg.batches[facadeKey];
    const TR = reg.batches.trim;
    const body = (w, hh, d, lx, ly, lz) => lbox(FB, s, w, hh, d, lx, ly, lz, true);
    const trim = (w, hh, d, lx, ly, lz, c) => lbox(TR, s, w, hh, d, lx, ly, lz, c || trimC);

    // ---- main mass ----
    body(s.w, h, s.d, 0, h / 2, 0);
    // foundation strip
    trim(s.w + 0.16, 0.35, s.d + 0.16, 0, 0.17, 0, 0x8A8278);

    // ---- roofline ----
    if (s.style === 'chalet') {
      gableRoof(s, reg, r, h, facadeKey);
    } else {
      // flat roof: membrane + parapet cap
      trim(s.w - 0.4, 0.12, s.d - 0.4, 0, h + 0.06, 0, 0x4A463E);
      trim(s.w + 0.34, 0.22, s.d + 0.34, 0, h + 0.16, 0, trimC.clone().multiplyScalar(0.8));
      if (s.w > 9 && r() > 0.35) { // rooftop units
        trim(1.7, 1.0, 1.4, (r() - 0.5) * s.w * 0.5, h + 0.7, (r() - 0.5) * s.d * 0.4, 0x8C8678);
        trim(0.5, 0.9, 0.5, (r() - 0.5) * s.w * 0.4, h + 0.6, (r() - 0.5) * s.d * 0.4, 0x6A645C);
      }
      if (r() > 0.55) { // brick chimney flue
        lbox(reg.batches.brick_red, s, 0.8, 1.6, 0.8, s.w * 0.32, h + 0.7, -s.d * 0.28, true);
      }
    }

    if (s.style === 'falsefront') {
      // raised front parapet: flat, stepped, or peaked
      const kind = r();
      const pw = s.w + 0.3;
      if (kind < 0.4) {
        body(pw, 2.2, 0.45, 0, h + 1.0, front - 0.12);
      } else if (kind < 0.75) { // stepped
        body(pw, 1.5, 0.45, 0, h + 0.65, front - 0.12);
        body(pw * 0.55, 1.4, 0.45, 0, h + 1.9, front - 0.12);
      } else { // center peak
        body(pw, 1.6, 0.45, 0, h + 0.7, front - 0.12);
        body(pw * 0.36, 1.1, 0.45, 0, h + 2.0, front - 0.12);
      }
      cornice(s, reg, pw, h + (kind < 0.4 ? 2.2 : kind < 0.75 ? 2.7 : 2.6), front - 0.12, trimC, r);
    } else if (s.style === 'brick' || s.style === 'retail' || s.style === 'lodge') {
      cornice(s, reg, s.w + 0.3, h + 0.28, front - 0.05, trimC, r);
    }

    if (s.style === 'lodge') {
      lbox(reg.batches.stone, s, s.w + 0.4, 2.0, s.d + 0.4, 0, 1.0, 0, true);
    }

    // ---- ground floor ----
    if (s.storefront !== false) {
      storefront(s, reg, trimC, r);
    } else {
      housefront(s, reg, trimC, r);
    }

    // ---- upper windows ----
    for (let f = 1; f < floors; f++) {
      const wy = f * fh + 1.7;
      const n = Math.max(2, Math.floor(s.w / 2.7));
      for (let i = 0; i < n; i++) {
        framedWindow(s, reg, -s.w / 2 + (s.w / n) * (i + 0.5), wy, front, 1.1, 1.8, trimC, r);
      }
    }
    if (s.sideWindows) {
      sideGlazing(s, reg, floors, fh, trimC, r);
    }

    // ---- awning ----
    if (s.awning) {
      const key = typeof s.awning === 'string' ? s.awning : pick(r, AWNINGS);
      const aw = s.w - 1.4;
      const g = new THREE.BoxGeometry(aw, 0.1, 1.8);
      g.applyMatrix4(new THREE.Matrix4().makeRotationX(0.34));
      reg.batches[key].add(g, mat4(s, 0, 3.12, front + 0.9), 0xFFFFFF, [aw * 0.5, 1]);
      // valance
      const v = new THREE.BoxGeometry(aw, 0.28, 0.06);
      reg.batches[key].add(v, mat4(s, 0, 2.78, front + 1.74), 0xFFFFFF, [aw * 0.5, 0.25]);
    }

    // ---- porch / boardwalk roof ----
    if (s.porch) {
      trim(s.w + 0.6, 0.14, 2.8, 0, 3.5, front + 1.4);
      lbox(reg.batches.roof_metal_grey, s, s.w + 0.8, 0.08, 3.0, 0, 3.62, front + 1.4, true);
      const n = Math.max(2, Math.round(s.w / 3.6));
      for (let i = 0; i <= n; i++) {
        trim(0.16, 3.5, 0.16, -s.w / 2 + (s.w / n) * i, 1.75, front + 2.5);
      }
      trim(s.w + 0.4, 0.1, 0.1, 0, 1.0, front + 2.5); // rail
    }

    // ---- signage ----
    if (s.sign) makeSign(s, signs, front, h);
  }

  function cornice(s, reg, w, y, z, trimC, r) {
    const TR = reg.batches.trim;
    lbox(TR, s, w + 0.4, 0.34, 0.7, 0, y, z + 0.12, trimC);
    lbox(TR, s, w + 0.2, 0.16, 0.55, 0, y - 0.26, z + 0.08, trimC.clone().multiplyScalar(0.85));
    // dentils
    const n = Math.floor(w / 0.62);
    for (let i = 0; i < n; i++) {
      lbox(TR, s, 0.22, 0.2, 0.3, -w / 2 + 0.3 + i * 0.62, y - 0.42, z + 0.18, trimC);
    }
  }

  function framedWindow(s, reg, lx, ly, front, ww, wh, trimC, r) {
    const TR = reg.batches.trim;
    const G = reg.batches[r() > 0.45 ? 'glassLit' : 'glassDark'];
    lbox(G, s, ww, wh, 0.08, lx, ly, front + 0.02, true);
    // frame
    const fw = 0.12;
    lbox(TR, s, ww + fw * 2, fw, 0.18, lx, ly + wh / 2 + fw / 2, front + 0.05, trimC);
    lbox(TR, s, ww + fw * 2, fw, 0.18, lx, ly - wh / 2 - fw / 2, front + 0.05, trimC);
    lbox(TR, s, fw, wh, 0.18, lx - ww / 2 - fw / 2, ly, front + 0.05, trimC);
    lbox(TR, s, fw, wh, 0.18, lx + ww / 2 + fw / 2, ly, front + 0.05, trimC);
    // mullion cross
    lbox(TR, s, ww, 0.05, 0.12, lx, ly, front + 0.045, trimC);
    lbox(TR, s, 0.05, wh, 0.12, lx, ly, front + 0.045, trimC);
    // sill
    lbox(TR, s, ww + 0.4, 0.1, 0.26, lx, ly - wh / 2 - fw - 0.05, front + 0.1, trimC.clone().multiplyScalar(0.9));
  }

  function storefront(s, reg, trimC, r) {
    const TR = reg.batches.trim;
    const front = s.d / 2;
    const gw = s.w - 1.2, gh = 2.45;
    const doorW = 1.15;
    const doorX = (r() < 0.5 ? -1 : 1) * (gw / 2 - doorW / 2 - 0.25);
    const G = reg.batches[r() > 0.3 ? 'glassLit' : 'glassDark'];

    // bulkhead (kick panel)
    lbox(TR, s, gw, 0.55, 0.18, 0, 0.3, front + 0.04, trimC.clone().multiplyScalar(0.7));
    // display glass with vertical mullions
    lbox(G, s, gw, gh - 0.55, 0.08, 0, 0.55 + (gh - 0.55) / 2, front + 0.03, true);
    const cols = Math.max(2, Math.round(gw / 2.2));
    for (let i = 0; i <= cols; i++) {
      lbox(TR, s, 0.1, gh, 0.2, -gw / 2 + (gw / cols) * i, gh / 2 + 0.28, front + 0.06, trimC);
    }
    // transom band
    lbox(G, s, gw, 0.45, 0.08, 0, gh + 0.5, front + 0.03, true);
    lbox(TR, s, gw + 0.3, 0.1, 0.22, 0, gh + 0.27, front + 0.06, trimC);
    // recessed door
    lbox(TR, s, doorW, 2.25, 0.1, doorX, 1.4, front - 0.32, trimC.clone().multiplyScalar(0.55));
    lbox(reg.batches.glassDark, s, doorW - 0.3, 1.3, 0.06, doorX, 1.7, front - 0.27, true);
    lbox(TR, s, 0.12, 2.5, 0.5, doorX - doorW / 2 - 0.06, 1.25, front - 0.12, trimC);
    lbox(TR, s, 0.12, 2.5, 0.5, doorX + doorW / 2 + 0.06, 1.25, front - 0.12, trimC);
    lbox(TR, s, doorW + 0.24, 0.12, 0.5, doorX, 2.56, front - 0.12, trimC);
    // step
    lbox(TR, s, doorW + 0.3, 0.08, 0.6, doorX, 0.04, front + 0.1, 0x8A8278);
    // sign band
    lbox(TR, s, s.w, 0.95, 0.26, 0, gh + 1.25, front - 0.02, trimC.clone().multiplyScalar(0.78));
  }

  function housefront(s, reg, trimC, r) {
    const TR = reg.batches.trim;
    const front = s.d / 2;
    // door with frame
    lbox(TR, s, 1.1, 2.25, 0.14, 0, 1.15, front + 0.03, trimC.clone().multiplyScalar(0.5));
    lbox(TR, s, 1.34, 0.12, 0.2, 0, 2.33, front + 0.05, trimC);
    lbox(TR, s, 0.12, 2.3, 0.2, -0.67, 1.18, front + 0.05, trimC);
    lbox(TR, s, 0.12, 2.3, 0.2, 0.67, 1.18, front + 0.05, trimC);
    for (const dx of [-1, 1]) {
      framedWindow(s, reg, dx * s.w * 0.28, 1.75, front, 1.15, 1.35, trimC, r);
    }
  }

  function sideGlazing(s, reg, floors, fh, trimC, r) {
    for (let f = 0; f < floors; f++) {
      const wy = f * fh + 1.9;
      const n = Math.max(2, Math.floor(s.d / 3.4));
      for (let i = 0; i < n; i++) {
        const wz = -s.d / 2 + (s.d / n) * (i + 0.5);
        const sideX = (s.sideWindows === 'left' ? -1 : 1) * (s.w / 2 + 0.02);
        const G = reg.batches[r() > 0.5 ? 'glassLit' : 'glassDark'];
        G.add(new THREE.BoxGeometry(0.08, 1.6, 1.1), mat4(s, sideX, wy, wz), 0xFFFFFF);
        reg.batches.trim.add(new THREE.BoxGeometry(0.14, 0.1, 1.4), mat4(s, sideX + 0.02, wy - 0.85, wz), trimC);
      }
    }
  }

  function gableRoof(s, reg, r, h, facadeKey) {
    const pick = KW.util.pick;
    const key = pick(r, ['roof_shingle', 'roof_metal_green', 'roof_metal_red', 'roof_metal_grey']);
    const RF = reg.batches[key];
    const ang = 0.58, rl = s.d * 0.64, rw = s.w + 1.4;
    for (const sgn of [-1, 1]) {
      const geo = new THREE.BoxGeometry(rw, 0.22, rl);
      geo.applyMatrix4(new THREE.Matrix4().makeRotationX(sgn * ang));
      geo.translate(0, rl * 0.40 * Math.sin(ang), sgn * rl * 0.40 * Math.cos(ang));
      RF.add(geo, mat4(s, 0, h - 0.15, 0), 0xFFFFFF, [rw * 0.3, rl * 0.3]);
    }
    // ridge cap
    reg.batches.trim.add(new THREE.BoxGeometry(rw, 0.16, 0.3),
      mat4(s, 0, h - 0.15 + rl * 0.40 * Math.sin(ang) + 0.1, 0), 0x3A352E);
    // gable infill (triangle approximated by stacked, narrowing slabs)
    const FB = reg.batches[facadeKey || 'clap_brown'];
    const gh = rl * 0.38;
    for (let i = 0; i < 4; i++) {
      const t = i / 4;
      FB.add(new THREE.BoxGeometry(s.w - 0.2, gh / 4 + 0.02, (s.d - 0.5) * (1 - t)),
        mat4(s, 0, h + gh * t + gh / 8, 0), 0xFFFFFF, [s.w * 0.32, gh * 0.1]);
    }
    // chimney
    if (r() > 0.4) {
      reg.batches.stone.add(new THREE.BoxGeometry(1.0, gh + 2.2, 1.0),
        mat4(s, s.w * 0.3, h + (gh + 2.2) / 2 - 0.4, 0), true);
    }
  }

  function makeSign(s, signs, front, h) {
    const t = KW.textures.sign(s.sign.text, s.sign.style || 'paint', s.sign.sub);
    const sm = new THREE.MeshLambertMaterial({ map: t });
    if (s.sign.style === 'neon') {
      sm.emissive = new THREE.Color(0xFF8A5C);
      sm.emissiveMap = t;
      sm.userData = { dayGlow: 0.18, nightGlow: 1.0 };
      KW.env.emissiveMats.push(sm);
    }
    const sw = Math.min(s.w * 0.82, 9), sh = sw / 4;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(sw, sh), sm);
    const p = new THREE.Vector3(0, 0, front + 0.18)
      .applyMatrix4(new THREE.Matrix4().makeRotationY(s.ry || 0));
    mesh.position.set(s.x + p.x, (s.sign.y || 3.6) + sh / 2 - 0.5, s.z + p.z);
    mesh.rotation.y = s.ry || 0;
    signs.push(mesh);
    if (s.sign.hang) {
      const hm = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 0.8), sm.clone());
      hm.material.side = THREE.DoubleSide;
      const hp = new THREE.Vector3(s.w / 2 - 1.2, 0, front + 1.0)
        .applyMatrix4(new THREE.Matrix4().makeRotationY(s.ry || 0));
      hm.position.set(s.x + hp.x, 3.1, s.z + hp.z);
      hm.rotation.y = (s.ry || 0) + Math.PI / 2;
      signs.push(hm);
    }
  }

  return B;
})();
