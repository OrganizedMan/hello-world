/* Street furniture: lamps, benches, planters, parked vehicles, street &
 * stop signs, power poles with sagging lines, picnic tables, string
 * lights. Everything merges into a few meshes per district. */
KW.props = (function () {
  const P = {};
  let batch, glowBatch, matGlow, matSolid;
  const signMeshes = [];
  const wirePts = [];
  const streetNameTex = {};
  let stopTex = null;

  P.begin = function () {
    batch = new KW.util.GeoBatch();
    glowBatch = new KW.util.GeoBatch();
    if (!matSolid) {
      matSolid = new THREE.MeshLambertMaterial({ vertexColors: true });
      matGlow = new THREE.MeshLambertMaterial({
        color: 0xFFF2CF, emissive: 0xFFDF9A, emissiveIntensity: 0.15,
      });
      matGlow.userData = { dayGlow: 0.15, nightGlow: 2.4 };
      KW.env.emissiveMats.push(matGlow);
    }
  };

  P.flush = function (scene) {
    const g = batch.merge();
    if (g) {
      const m = new THREE.Mesh(g, matSolid);
      m.castShadow = true; m.receiveShadow = true;
      scene.add(m);
    }
    const gg = glowBatch.merge();
    if (gg) scene.add(new THREE.Mesh(gg, matGlow));
    for (const s of signMeshes) scene.add(s);
    signMeshes.length = 0;
    if (wirePts.length) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(wirePts), 3));
      scene.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: 0x14110E })));
      wirePts.length = 0;
    }
  };

  // place an oriented box: rotation ry about (x, z)
  function put(w, h, d, x, y, z, lx, ly, lz, ry, c) {
    const g = new THREE.BoxGeometry(w, h, d);
    const v = new THREE.Vector3(lx, ly, lz).applyAxisAngle(new THREE.Vector3(0, 1, 0), ry || 0);
    const mm = new THREE.Matrix4().makeRotationY(ry || 0).setPosition(x + v.x, ly, z + v.z);
    batch.add(g, mm, c);
  }
  function putCyl(r0, r1, h, x, y, z, c, rz) {
    const g = new THREE.CylinderGeometry(r0, r1, h, 10);
    const m = new THREE.Matrix4();
    if (rz) m.makeRotationZ(rz);
    m.setPosition(x, y, z);
    batch.add(g, m, c);
  }

  P.lamp = function (x, z) {
    putCyl(0.26, 0.3, 0.18, x, 0.09, z, 0x1D1D1F);
    putCyl(0.06, 0.09, 4.4, x, 2.2, z, 0x1D1D1F);
    put(0.46, 0.1, 0.46, x, 4.45, z, 0, 4.45, 0, 0, 0x1D1D1F);
    glowBatch.box(0.3, 0.5, 0.3, x, 4.15, z, 0xFFF2CF);
    put(0.55, 0.14, 0.55, x, 4.55, z, 0, 4.55, 0, 0, 0x1D1D1F);
    // hanging flower basket — Ketchum does this all summer
    put(0.34, 0.22, 0.34, x + 0.42, 3.45, z, 0, 3.45, 0, 0, 0x4D3826);
    put(0.4, 0.16, 0.4, x + 0.42, 3.6, z, 0, 3.6, 0, 0, 0x9E3D52);
  };

  P.bench = function (x, z, ry) {
    put(1.8, 0.07, 0.5, x, 0.45, z, 0, 0.45, 0, ry, 0x6E4F30);
    put(1.8, 0.5, 0.07, x, 0.78, z, 0, 0.78, -0.26, ry, 0x6E4F30);
    put(0.07, 0.45, 0.5, x, 0.22, z, -0.8, 0.22, 0, ry, 0x222222);
    put(0.07, 0.45, 0.5, x, 0.22, z, 0.8, 0.22, 0, ry, 0x222222);
  };

  P.planter = function (x, z) {
    put(1.1, 0.55, 1.1, x, 0.27, z, 0, 0.27, 0, 0, 0x6F675C);
    put(0.9, 0.3, 0.9, x, 0.62, z, 0, 0.62, 0, 0, 0x4D6B2E);
    const r = KW.util.rng((x * 31 + z * 17) | 0);
    for (let i = 0; i < 5; i++) {
      put(0.1, 0.12, 0.1, x, 0.83, z, (r() - 0.5) * 0.7, 0.83, (r() - 0.5) * 0.7, 0,
        [0xD8533C, 0xE0B33C, 0xB05CCC, 0xE8E4DA, 0xD8533C][i]);
    }
  };

  P.picnicTable = function (x, z, ry) {
    const wood = 0x8A6A44;
    put(2.2, 0.08, 0.9, x, 0.74, z, 0, 0.74, 0, ry, wood);
    for (const sgn of [-1, 1]) {
      put(2.2, 0.06, 0.3, x, 0.45, z, 0, 0.45, sgn * 0.75, ry, wood);
      put(0.1, 0.74, 1.9, x, 0.37, z, sgn * 0.9, 0.37, 0, ry, 0x6E5136);
    }
  };

  /** type: 0 SUV, 1 pickup, 2 sedan */
  P.car = function (x, z, ry, color, type) {
    const dark = new THREE.Color(color).multiplyScalar(0.8);
    const glass = 0x1A2026;
    type = type || 0;
    if (type === 1) { // pickup
      put(1.92, 0.7, 5.0, x, 0.82, z, 0, 0.82, 0, ry, color);
      put(1.82, 0.78, 1.7, x, 1.56, z, 0, 1.56, 0.55, ry, dark);
      put(1.84, 0.5, 1.6, x, 1.62, z, 0, 1.62, 0.55, ry, glass);
      put(1.7, 0.45, 2.1, x, 1.18, z, 0, 1.18, -1.35, ry, dark); // bed walls
    } else if (type === 2) { // sedan
      put(1.8, 0.55, 4.4, x, 0.62, z, 0, 0.62, 0, ry, color);
      put(1.66, 0.55, 2.2, x, 1.12, z, 0, 1.12, 0.1, ry, dark);
      put(1.68, 0.42, 2.1, x, 1.14, z, 0, 1.14, 0.1, ry, glass);
    } else { // SUV
      put(1.9, 0.85, 4.5, x, 0.8, z, 0, 0.8, 0, ry, color);
      put(1.78, 0.72, 2.9, x, 1.55, z, 0, 1.55, -0.2, ry, dark);
      put(1.8, 0.5, 2.8, x, 1.58, z, 0, 1.58, -0.2, ry, glass);
      put(0.7, 0.12, 1.6, x, 2.0, z, 0, 2.0, -0.2, ry, 0x2A2A2A); // roof box
    }
    // wheels
    const wb = type === 1 ? 1.65 : 1.4;
    for (const [lx, lz] of [[-0.86, wb], [0.86, wb], [-0.86, -wb], [0.86, -wb]]) {
      const v = new THREE.Vector3(lx, 0, lz).applyAxisAngle(new THREE.Vector3(0, 1, 0), ry || 0);
      const g = new THREE.CylinderGeometry(0.36, 0.36, 0.24, 10);
      const m = new THREE.Matrix4().makeRotationZ(Math.PI / 2);
      m.premultiply(new THREE.Matrix4().makeRotationY(ry || 0));
      m.setPosition(x + v.x, 0.36, z + v.z);
      batch.add(g, m, 0x141414);
    }
  };

  P.streetSign = function (x, z, nameNS, nameEW, withStop) {
    putCyl(0.05, 0.05, 3.4, x, 1.7, z, 0x3A3F45);
    for (const [name, ry] of [[nameNS, 0], [nameEW, Math.PI / 2]]) {
      if (!name) continue;
      if (!streetNameTex[name]) streetNameTex[name] = KW.textures.streetName(name);
      const m = new THREE.Mesh(
        new THREE.PlaneGeometry(1.7, 0.42),
        new THREE.MeshLambertMaterial({ map: streetNameTex[name], side: THREE.DoubleSide })
      );
      m.position.set(x, ry ? 3.0 : 3.3, z);
      m.rotation.y = ry;
      signMeshes.push(m);
    }
    if (withStop) {
      if (!stopTex) stopTex = KW.textures.stopSign();
      const m = new THREE.Mesh(
        new THREE.PlaneGeometry(0.75, 0.75),
        new THREE.MeshLambertMaterial({ map: stopTex, transparent: true, side: THREE.DoubleSide })
      );
      m.position.set(x, 2.4, z);
      m.rotation.y = withStop === true ? 0 : withStop;
      signMeshes.push(m);
    }
  };

  P.hydrant = function (x, z) {
    putCyl(0.14, 0.16, 0.7, x, 0.35, z, 0xB33024);
    putCyl(0.1, 0.1, 0.18, x, 0.78, z, 0xB33024);
    put(0.42, 0.12, 0.14, x, 0.5, z, 0, 0.5, 0, 0, 0xB33024);
  };

  P.plaqueMarker = function (x, z) {
    put(0.12, 1.0, 0.12, x, 0.5, z, 0, 0.5, 0, 0, 0x4A3826);
    const g = new THREE.BoxGeometry(0.66, 0.5, 0.05);
    g.applyMatrix4(new THREE.Matrix4().makeRotationX(-0.5));
    batch.add(g, new THREE.Matrix4().setPosition(x, 1.12, z), 0x8A6D3B);
    glowBatch.box(0.56, 0.36, 0.03, x, 1.14, z + 0.06, 0xC9A85C);
  };

  P.flagpole = function (x, z) {
    putCyl(0.05, 0.07, 7.5, x, 3.75, z, 0xB9BCC2);
    put(1.5, 0.95, 0.04, x, 6.8, z, 0.78, 6.8, 0, 0, 0xB33A3A);
  };

  function sagLine(x0, y0, z0, x1, y1, z1, sag, segs) {
    let px = x0, py = y0, pz = z0;
    for (let i = 1; i <= segs; i++) {
      const t = i / segs;
      const nx = x0 + (x1 - x0) * t;
      const nz = z0 + (z1 - z0) * t;
      const ny = y0 + (y1 - y0) * t - Math.sin(t * Math.PI) * sag;
      wirePts.push(px, py, pz, nx, ny, nz);
      px = nx; py = ny; pz = nz;
    }
  }

  /** Power poles with two sagging wires from (x0,z0) to (x1,z1). */
  P.powerRun = function (x0, z0, x1, z1) {
    const len = Math.hypot(x1 - x0, z1 - z0);
    const n = Math.max(2, Math.round(len / 42));
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const px = x0 + (x1 - x0) * t, pz = z0 + (z1 - z0) * t;
      putCyl(0.09, 0.12, 7.6, px, 3.8, pz, 0x4A3E30);
      const dir = Math.atan2(x1 - x0, z1 - z0);
      put(1.6, 0.1, 0.1, px, 7.2, pz, 0, 7.2, 0, dir, 0x4A3E30);
      pts.push([px, pz, dir]);
    }
    for (let i = 0; i < n; i++) {
      const [ax, az, dir] = pts[i], [bx, bz] = pts[i + 1];
      const ox = Math.cos(dir) * 0.7, oz = -Math.sin(dir) * 0.7;
      sagLine(ax + ox, 7.25, az + oz, bx + ox, 7.25, bz + oz, 0.8, 7);
      sagLine(ax - ox, 7.25, az - oz, bx - ox, 7.25, bz - oz, 0.8, 7);
    }
  };

  /** Festoon/string lights between two points (e.g. over a beer garden). */
  P.stringLights = function (x0, y0, z0, x1, y1, z1) {
    const segs = 9;
    sagLine(x0, y0, z0, x1, y1, z1, 0.5, segs);
    for (let i = 1; i < segs; i++) {
      const t = i / segs;
      const bx = x0 + (x1 - x0) * t;
      const bz = z0 + (z1 - z0) * t;
      const by = y0 + (y1 - y0) * t - Math.sin(t * Math.PI) * 0.5 - 0.09;
      glowBatch.box(0.09, 0.12, 0.09, bx, by, bz, 0xFFE2A8);
    }
  };

  return P;
})();
