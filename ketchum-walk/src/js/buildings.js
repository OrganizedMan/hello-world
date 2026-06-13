/* Data-driven building generator. Whole districts of buildings are merged
 * into a handful of meshes (body / lit glass / dark glass) to keep draw
 * calls low; landmark signage gets individual textured planes. */
KW.buildings = (function () {
  const B = {};

  let matBody, matGlassLit, matGlassDark;
  function materials() {
    if (matBody) return;
    matBody = new THREE.MeshLambertMaterial({ map: KW.textures.grain(), vertexColors: true });
    matGlassLit = new THREE.MeshLambertMaterial({
      color: 0x36444f, emissive: 0xffc97a, emissiveIntensity: 0,
    });
    matGlassLit.userData = { dayGlow: 0, nightGlow: 1.4 };
    matGlassDark = new THREE.MeshLambertMaterial({ color: 0x232d36 });
    KW.env.emissiveMats.push(matGlassLit);
  }

  /**
   * Build all `specs` into `scene`. Each spec:
   * { x, z, w, d, ry, floors|h, style, color, trim, roofColor,
   *   sign: {text, style, sub, hang}, awning: hexColor, porch: bool,
   *   noCollide: bool }
   * Local space: width w on X, depth d on Z, the FRONT faces local +Z;
   * ry rotates the building (0 = front faces south/+Z world).
   */
  B.generate = function (specs, scene, colliders) {
    materials();
    const body = new KW.util.GeoBatch();
    const glassLit = new KW.util.GeoBatch();
    const glassDark = new KW.util.GeoBatch();
    const signs = [];
    const r = KW.util.rng(1337);

    for (const s of specs) {
      buildOne(s, body, glassLit, glassDark, signs, r);
      if (!s.noCollide) colliders.push(footprint(s));
    }

    const bodyMesh = new THREE.Mesh(body.merge(), matBody);
    bodyMesh.castShadow = true; bodyMesh.receiveShadow = true;
    scene.add(bodyMesh);
    const gl = glassLit.merge();
    if (gl) scene.add(new THREE.Mesh(gl, matGlassLit));
    const gd = glassDark.merge();
    if (gd) scene.add(new THREE.Mesh(gd, matGlassDark));
    for (const m of signs) scene.add(m);
  };

  function footprint(s) {
    const hw = s.w / 2 + 0.05, hd = s.d / 2 + 0.05;
    const cos = Math.abs(Math.cos(s.ry || 0)), sin = Math.abs(Math.sin(s.ry || 0));
    const ex = hw * cos + hd * sin, ez = hw * sin + hd * cos;
    return { minX: s.x - ex, maxX: s.x + ex, minZ: s.z - ez, maxZ: s.z + ez };
  }

  function mat4(s, lx, ly, lz, rotY) {
    const m = new THREE.Matrix4().makeRotationY(s.ry || 0);
    const v = new THREE.Vector3(lx, ly, lz).applyMatrix4(new THREE.Matrix4().makeRotationY(s.ry || 0));
    if (rotY) m.multiply(new THREE.Matrix4().makeRotationY(rotY));
    m.setPosition(s.x + v.x, ly, s.z + v.z);
    return m;
  }

  // local-space box helper
  function lbox(batch, s, w, h, d, lx, ly, lz, color, uvScale) {
    const g = new THREE.BoxGeometry(w, h, d);
    batch.add(g, mat4(s, lx, ly, lz), color, [Math.max(w, d) * (uvScale || 0.35), h * (uvScale || 0.35)]);
  }
  function lplane(batch, s, w, h, lx, ly, lz, color) {
    const g = new THREE.PlaneGeometry(w, h);
    batch.add(g, mat4(s, lx, ly, lz), color);
  }

  function buildOne(s, body, glassLit, glassDark, signs, r) {
    const floors = s.floors || 1;
    const fh = s.floorH || 3.4;
    const h = s.h || floors * fh + 0.6;
    const col = new THREE.Color(s.color || 0xcfc4ae);
    const trim = new THREE.Color(s.trim || 0x55483a);
    const front = s.d / 2;

    // main body
    lbox(body, s, s.w, h, s.d, 0, h / 2, 0, col);

    // roof cap (slightly darker)
    if (s.style !== 'chalet') {
      lbox(body, s, s.w + 0.3, 0.35, s.d + 0.3, 0, h + 0.12, 0, col.clone().multiplyScalar(0.55));
      // roof clutter
      if (s.w > 10 && r() > 0.4) {
        lbox(body, s, 1.6, 1.0, 1.6, (r() - 0.5) * s.w * 0.5, h + 0.8, (r() - 0.5) * s.d * 0.5, 0x8c8678);
      }
    }

    if (s.style === 'falsefront') {
      // raised front parapet with cornice — classic mining-town storefront
      lbox(body, s, s.w + 0.4, 2.4, 0.5, 0, h + 1.0, front - 0.1, col.clone().multiplyScalar(1.06));
      lbox(body, s, s.w + 0.8, 0.5, 0.8, 0, h + 2.3, front - 0.1, trim);
    } else if (s.style === 'brick' || s.style === 'lodge') {
      lbox(body, s, s.w + 0.5, 0.7, s.d + 0.5, 0, h + 0.3, 0, trim);
    }
    if (s.style === 'lodge') {
      // stone base band
      lbox(body, s, s.w + 0.35, 1.6, s.d + 0.35, 0, 0.8, 0, 0x7a7166);
    }
    if (s.style === 'chalet') {
      // gabled roof from two sloped slabs
      const ang = 0.62, rl = s.d * 0.62, rw = s.w + 1.2, rc = new THREE.Color(s.roofColor || 0x4a423a);
      for (const sgn of [-1, 1]) {
        const geo = new THREE.BoxGeometry(rw, 0.3, rl);
        const lm = new THREE.Matrix4().makeRotationX(sgn * ang);
        geo.applyMatrix4(lm);
        geo.translate(0, 0, sgn * rl * 0.40 * Math.cos(ang));
        geo.translate(0, rl * 0.40 * Math.sin(ang), 0);
        body.add(geo, mat4(s, 0, h - 0.2, 0), rc, [rw * 0.3, rl * 0.3]);
      }
      // gable infill
      lbox(body, s, s.w, rl * 0.42, s.d - 0.6, 0, h + rl * 0.18, 0, col.clone().multiplyScalar(0.96));
    }

    // ---- storefront (ground floor, front face) ----
    if (s.storefront !== false) {
      const gw = s.w - 1.6, gh = 2.5;
      const gb = r() > 0.35 ? glassLit : glassDark;
      lbox(gb, s, gw, gh, 0.12, 0, 0.5 + gh / 2, front + 0.05, 0xffffff);
      // kick panel + entry pillars
      lbox(body, s, gw, 0.55, 0.2, 0, 0.28, front + 0.06, trim);
      const cols = Math.max(2, Math.round(gw / 3.4));
      for (let i = 0; i <= cols; i++) {
        lbox(body, s, 0.22, gh + 0.8, 0.26, -gw / 2 + (gw / cols) * i, (gh + 0.8) / 2 + 0.3, front + 0.07, trim);
      }
      // sign band
      lbox(body, s, s.w, 0.9, 0.3, 0, gh + 1.15, front - 0.02, col.clone().multiplyScalar(0.8));
    } else {
      // house/chalet front: door + two windows
      lbox(body, s, 1.2, 2.3, 0.16, 0, 1.15, front + 0.04, trim);
      for (const dx of [-1, 1]) {
        const gb = r() > 0.5 ? glassLit : glassDark;
        lbox(gb, s, 1.2, 1.3, 0.1, dx * s.w * 0.28, 1.8, front + 0.04, 0xffffff);
        lbox(body, s, 1.5, 0.12, 0.14, dx * s.w * 0.28, 2.55, front + 0.05, trim);
      }
    }

    // ---- upper-floor windows, front + maybe sides ----
    for (let f = 1; f < floors; f++) {
      const wy = f * fh + 1.6;
      const n = Math.max(2, Math.floor(s.w / 2.6));
      for (let i = 0; i < n; i++) {
        const wx = -s.w / 2 + (s.w / n) * (i + 0.5);
        const gb = r() > 0.45 ? glassLit : glassDark;
        lbox(gb, s, 1.1, 1.7, 0.1, wx, wy, front + 0.04, 0xffffff);
        lbox(body, s, 1.4, 0.14, 0.16, wx, wy + 0.95, front + 0.05, trim); // lintel
        lbox(body, s, 1.4, 0.14, 0.16, wx, wy - 0.95, front + 0.05, trim); // sill
      }
    }
    if (s.sideWindows) {
      for (let f = 0; f < floors; f++) {
        const wy = f * fh + 1.9;
        const n = Math.max(2, Math.floor(s.d / 3.2));
        for (let i = 0; i < n; i++) {
          const wz = -s.d / 2 + (s.d / n) * (i + 0.5);
          const sideX = (s.sideWindows === 'left' ? -1 : 1) * (s.w / 2 + 0.04);
          const gb = r() > 0.5 ? glassLit : glassDark;
          const g = new THREE.BoxGeometry(0.1, 1.6, 1.1);
          gb.add(g, mat4(s, sideX, wy, wz), 0xffffff);
        }
      }
    }

    // ---- awning ----
    if (s.awning) {
      const aw = s.w - 1.2;
      const g = new THREE.BoxGeometry(aw, 0.12, 1.7);
      g.applyMatrix4(new THREE.Matrix4().makeRotationX(0.32));
      body.add(g, mat4(s, 0, 3.05, front + 0.85), s.awning, [aw * 0.3, 0.6]);
    }

    // ---- porch (boardwalk roof on posts) ----
    if (s.porch) {
      lbox(body, s, s.w + 0.6, 0.18, 2.6, 0, 3.4, front + 1.3, trim);
      const n = Math.max(2, Math.round(s.w / 4));
      for (let i = 0; i <= n; i++) {
        lbox(body, s, 0.18, 3.4, 0.18, -s.w / 2 + (s.w / n) * i, 1.7, front + 2.3, trim);
      }
    }

    // ---- signage ----
    if (s.sign) {
      const t = KW.textures.sign(s.sign.text, s.sign.style || 'paint', s.sign.sub);
      const sm = new THREE.MeshLambertMaterial({ map: t });
      if (s.sign.style === 'neon') {
        sm.emissive = new THREE.Color(0xff8a5c);
        sm.emissiveMap = t;
        sm.userData = { dayGlow: 0.18, nightGlow: 1.0 };
        KW.env.emissiveMats.push(sm);
      }
      const sw = Math.min(s.w * 0.82, 9), sh = sw / 4;
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(sw, sh), sm);
      const p = new THREE.Vector3(0, 0, front + 0.18)
        .applyMatrix4(new THREE.Matrix4().makeRotationY(s.ry || 0));
      mesh.position.set(s.x + p.x, (s.sign.y || 3.55) + sh / 2 - 0.5, s.z + p.z);
      mesh.rotation.y = s.ry || 0;
      signs.push(mesh);
      if (s.sign.hang) {
        // small perpendicular hanging sign
        const hm = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 0.8), sm.clone());
        hm.material.side = THREE.DoubleSide;
        const hp = new THREE.Vector3(s.w / 2 - 1.2, 3.1, front + 1.0)
          .applyMatrix4(new THREE.Matrix4().makeRotationY(s.ry || 0));
        hm.position.set(s.x + hp.x, 3.1, s.z + hp.z);
        hm.rotation.y = (s.ry || 0) + Math.PI / 2;
        signs.push(hm);
      }
    }
  }

  return B;
})();
