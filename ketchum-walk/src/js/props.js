/* Street furniture: lamps, benches, planters, parked cars, street signs.
 * Everything is merged into a few meshes per district. */
KW.props = (function () {
  const P = {};
  let batch, glowBatch, matGlow, matSolid;
  const signMeshes = [];
  const streetNameTex = {};

  P.begin = function () {
    batch = new KW.util.GeoBatch();
    glowBatch = new KW.util.GeoBatch();
    if (!matSolid) {
      matSolid = new THREE.MeshLambertMaterial({ vertexColors: true });
      matGlow = new THREE.MeshLambertMaterial({
        color: 0xfff2cf, emissive: 0xffdf9a, emissiveIntensity: 0.15,
      });
      matGlow.userData = { dayGlow: 0.15, nightGlow: 2.4 };
      KW.env.emissiveMats.push(matGlow);
    }
  };

  P.flush = function (scene) {
    const g = batch.merge();
    if (g) {
      const m = new THREE.Mesh(g, matSolid);
      m.castShadow = true;
      scene.add(m);
    }
    const gg = glowBatch.merge();
    if (gg) scene.add(new THREE.Mesh(gg, matGlow));
    for (const s of signMeshes) scene.add(s);
    signMeshes.length = 0;
  };

  P.lamp = function (x, z) {
    // black iron pole with a warm lantern head — Ketchum's downtown style
    batch.box(0.5, 0.18, 0.5, x, 0.09, z, 0x1d1d1f);
    batch.box(0.14, 4.4, 0.14, x, 2.2, z, 0x1d1d1f);
    batch.box(0.46, 0.1, 0.46, x, 4.45, z, 0x1d1d1f);
    glowBatch.box(0.32, 0.5, 0.32, x, 4.15, z, 0xfff2cf);
    batch.box(0.55, 0.16, 0.55, x, 4.55, z, 0x1d1d1f);
  };

  P.bench = function (x, z, ry) {
    const m = new THREE.Matrix4().makeRotationY(ry || 0);
    const put = (w, h, d, lx, ly, lz, c) => {
      const g = new THREE.BoxGeometry(w, h, d);
      const v = new THREE.Vector3(lx, ly, lz).applyAxisAngle(new THREE.Vector3(0, 1, 0), ry || 0);
      const mm = new THREE.Matrix4().makeRotationY(ry || 0).setPosition(x + v.x, ly, z + v.z);
      batch.add(g, mm, c);
    };
    put(1.8, 0.08, 0.5, 0, 0.45, 0, 0x6e4f30);
    put(1.8, 0.5, 0.08, 0, 0.78, -0.26, 0x6e4f30);
    put(0.08, 0.45, 0.5, -0.8, 0.22, 0, 0x222222);
    put(0.08, 0.45, 0.5, 0.8, 0.22, 0, 0x222222);
  };

  P.planter = function (x, z) {
    batch.box(1.1, 0.55, 1.1, x, 0.27, z, 0x6f675c);
    batch.box(0.9, 0.3, 0.9, x, 0.62, z, 0x4d6b2e);
    // wildflower dots
    const r = KW.util.rng((x * 31 + z * 17) | 0);
    for (let i = 0; i < 4; i++) {
      batch.box(0.1, 0.12, 0.1, x + (r() - 0.5) * 0.7, 0.83, z + (r() - 0.5) * 0.7,
        [0xd8533c, 0xe0b33c, 0xb05ccc, 0xe8e4da][i]);
    }
  };

  P.car = function (x, z, ry, color) {
    const put = (w, h, d, lx, ly, lz, c) => {
      const g = new THREE.BoxGeometry(w, h, d);
      const v = new THREE.Vector3(lx, ly, lz).applyAxisAngle(new THREE.Vector3(0, 1, 0), ry || 0);
      const mm = new THREE.Matrix4().makeRotationY(ry || 0).setPosition(x + v.x, ly, z + v.z);
      batch.add(g, mm, c);
    };
    // Ketchum runs on trucks and Subarus — boxy SUV silhouette
    put(1.9, 0.85, 4.4, 0, 0.78, 0, color);
    put(1.75, 0.7, 2.6, 0, 1.45, -0.25, new THREE.Color(color).multiplyScalar(0.85));
    put(1.78, 0.5, 2.4, 0, 1.5, -0.25, 0x1c2228); // glass band
    for (const [lx, lz] of [[-0.85, 1.4], [0.85, 1.4], [-0.85, -1.4], [0.85, -1.4]]) {
      put(0.25, 0.62, 0.62, lx, 0.31, lz, 0x161616);
    }
  };

  P.streetSign = function (x, z, nameNS, nameEW) {
    batch.box(0.09, 3.4, 0.09, x, 1.7, z, 0x3a3f45);
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
  };

  P.plaqueMarker = function (x, z) {
    // angled reader-board post marking an info spot
    batch.box(0.12, 1.0, 0.12, x, 0.5, z, 0x4a3826);
    const g = new THREE.BoxGeometry(0.66, 0.5, 0.05);
    g.applyMatrix4(new THREE.Matrix4().makeRotationX(-0.5));
    const m = new THREE.Matrix4().setPosition(x, 1.12, z);
    batch.add(g, m, 0x8a6d3b);
    glowBatch.box(0.56, 0.36, 0.03, x, 1.14, z + 0.06, 0xc9a85c);
  };

  P.flagpole = function (x, z) {
    batch.box(0.1, 7.5, 0.1, x, 3.75, z, 0xb9bcc2);
    batch.box(1.5, 0.95, 0.04, x + 0.78, 6.8, z, 0xb33a3a);
  };

  return P;
})();
