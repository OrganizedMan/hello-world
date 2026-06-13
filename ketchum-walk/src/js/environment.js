/* Sky, sun, fog, real heightfield terrain (Bald Mountain & the valley),
 * the Big Wood River, trees, and the day/night system. */
KW.env = (function () {
  const E = {};
  let sky, sun, hemi, stars, scene;
  let skyU;

  const DAY = {
    top: new THREE.Color(0x6F9CC9),
    horizon: new THREE.Color(0xF4C68F),
    sunColor: new THREE.Color(0xFFD9A6),
    sunIntensity: 1.25,
    hemiSky: new THREE.Color(0xBCD2E8),
    hemiGround: new THREE.Color(0x8A7A5A),
    hemiIntensity: 0.55,
  };
  const NIGHT = {
    top: new THREE.Color(0x060A18),
    horizon: new THREE.Color(0x16203A),
    sunColor: new THREE.Color(0x8FA6D4),
    sunIntensity: 0.18,
    hemiSky: new THREE.Color(0x223052),
    hemiGround: new THREE.Color(0x141210),
    hemiIntensity: 0.32,
  };

  const SUN_DIR_DAY = new THREE.Vector3(-0.75, 0.30, -0.35).normalize();  // low in the WNW
  const SUN_DIR_NIGHT = new THREE.Vector3(0.4, 0.55, 0.45).normalize();   // moon from the SE

  E.nightT = 0;
  E.emissiveMats = [];
  E.pointLights = []; // interior/exterior lamps that brighten at night

  // ---------------- terrain ----------------
  // Deterministic value-noise FBM.
  function hash2(ix, iz) {
    let h = (ix * 374761393 + iz * 668265263) | 0;
    h = (h ^ (h >> 13)) | 0;
    h = Math.imul(h, 1274126177);
    return ((h ^ (h >> 16)) >>> 0) / 4294967296;
  }
  function vnoise(x, z) {
    const ix = Math.floor(x), iz = Math.floor(z);
    const fx = x - ix, fz = z - iz;
    const sx = fx * fx * (3 - 2 * fx), sz = fz * fz * (3 - 2 * fz);
    const a = hash2(ix, iz), b = hash2(ix + 1, iz);
    const c = hash2(ix, iz + 1), d = hash2(ix + 1, iz + 1);
    return a + (b - a) * sx + (c - a) * sz + (a - b - c + d) * sx * sz;
  }
  function fbm(x, z, oct) {
    let v = 0, amp = 0.5, f = 1;
    for (let i = 0; i < oct; i++) {
      v += amp * vnoise(x * f, z * f);
      amp *= 0.5; f *= 2.1;
    }
    return v;
  }

  // Named peaks ringing the valley: [x, z, height, radius]
  const PEAKS = [
    [-1500, 1250, 870, 950],   // Bald Mountain (SW) — THE mountain
    [-2400, 300, 700, 1100],   // ridge behind Warm Springs
    [-1200, -1800, 640, 1100], // NW ridgeline
    [350, -2500, 680, 1300],   // Boulder foothills (N, up the valley)
    [1900, -1500, 620, 1200],  // NE toward Sun Valley / Dollar
    [2300, 300, 540, 1000],    // E ridge (Knob Hill side)
    [1500, 2100, 520, 1300],   // SE down-valley
    [-500, 2500, 600, 1300],   // S down-valley
  ];
  const BALDY = PEAKS[0];

  E.terrainHeight = function (x, z) {
    // flat town platform with smooth falloff
    const dx = Math.max(0, Math.max(-460 - x, x - 420), 0);
    const dzz = Math.max(0, Math.max(-720 - z, z - 200), 0);
    const dTown = Math.hypot(Math.max(0, dx), Math.max(0, dzz));
    const mask = THREE.MathUtils.smoothstep(dTown, 60, 600); // 0 in town → 1 outside

    let h = 0;
    for (const [px, pz, ph, pr] of PEAKS) {
      const d = Math.hypot(x - px, z - pz) / pr;
      h = Math.max(h, ph * Math.exp(-d * d * 1.6));
    }
    h += fbm(x * 0.0016, z * 0.0016, 4) * (60 + h * 0.55);
    h *= mask;
    // gentle valley floor undulation outside the street grid
    h += mask * fbm(x * 0.008 + 9, z * 0.008, 2) * 6;
    return h;
  };

  function buildTerrain() {
    const SIZE = 7200, SEG = 200;
    const geo = new THREE.PlaneGeometry(SIZE, SIZE, SEG, SEG);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position;
    const colors = new Float32Array(pos.count * 3);
    const col = new THREE.Color();
    const cGrass = new THREE.Color(0x7B8A52);
    const cSage = new THREE.Color(0x8A8E62);
    const cForest = new THREE.Color(0x3E5A34);
    const cForestDk = new THREE.Color(0x2F4628);
    const cRock = new THREE.Color(0x9A9288);
    const cRun = new THREE.Color(0x9FB068);

    // ski-run azimuths from Baldy's summit, fanning NE toward town
    const runDirs = [];
    for (let i = 0; i < 8; i++) runDirs.push(0.45 + i * 0.13);

    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), z = pos.getZ(i);
      const h = E.terrainHeight(x, z);
      pos.setY(i, h - 0.35);

      const n = fbm(x * 0.004 + 5, z * 0.004, 3);
      if (h < 14) col.copy(cGrass).lerp(cSage, n);
      else if (h < 90) col.copy(cSage).lerp(cForest, THREE.MathUtils.smoothstep(h, 18, 80) * (0.6 + n * 0.4));
      else col.copy(n > 0.52 ? cForest : cForestDk);
      if (h > 560) col.lerp(cRock, THREE.MathUtils.smoothstep(h, 560, 800));

      // paint Baldy's ski runs
      const bdx = x - BALDY[0], bdz = z - BALDY[1];
      const bd = Math.hypot(bdx, bdz);
      if (bd > 120 && bd < 1250 && h > 30) {
        const az = Math.atan2(bdx, -bdz); // bearing from summit
        for (const rd of runDirs) {
          const dAz = Math.abs(az - rd);
          if (dAz < 0.022 + (bd / 1250) * 0.012) {
            col.lerp(cRun, 0.85);
            break;
          }
        }
      }
      // speckle for tree texture at distance
      const sp = fbm(x * 0.03, z * 0.03, 2);
      col.multiplyScalar(0.88 + sp * 0.24);
      colors[i * 3] = col.r; colors[i * 3 + 1] = col.g; colors[i * 3 + 2] = col.b;
    }
    geo.computeVertexNormals();
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const det = KW.textures.terrainDetail();
    det.map.repeat.set(90, 90);
    const mat = new THREE.MeshLambertMaterial({ vertexColors: true, map: det.map });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.receiveShadow = true;
    scene.add(mesh);
  }

  function buildRiver() {
    // Big Wood River corridor along the west edge of town
    const wTex = KW.textures.water();
    wTex.map.repeat.set(3, 120);
    const water = new THREE.Mesh(
      new THREE.PlaneGeometry(22, 2400, 1, 60),
      new THREE.MeshPhongMaterial({ map: wTex.map, shininess: 90, specular: 0x88aabb })
    );
    water.rotation.x = -Math.PI / 2;
    const pos = water.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) { // meander
      pos.setX(i, pos.getX(i) + Math.sin(pos.getY(i) * 0.004) * 26);
    }
    water.position.set(-330, -0.95, -300);
    scene.add(water);
    // gravel banks
    const bank = KW.textures.gravel();
    bank.map.repeat.set(4, 160);
    const bankMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(46, 2400, 1, 60),
      new THREE.MeshLambertMaterial({ map: bank.map })
    );
    bankMesh.rotation.x = -Math.PI / 2;
    const bp = bankMesh.geometry.attributes.position;
    for (let i = 0; i < bp.count; i++) {
      bp.setX(i, bp.getX(i) + Math.sin(bp.getY(i) * 0.004) * 26);
    }
    bankMesh.position.set(-330, -1.1, -300);
    scene.add(bankMesh);
    E.riverPos = new THREE.Vector3(-330, 0, -300);
  }

  // ---------------- sky / lights ----------------
  E.init = function (sc) {
    scene = sc;

    skyU = {
      topColor: { value: DAY.top.clone() },
      horizonColor: { value: DAY.horizon.clone() },
      sunDir: { value: SUN_DIR_DAY.clone() },
      sunColor: { value: new THREE.Color(0xFFE9C4) },
      sunGlow: { value: 1.0 },
    };
    sky = new THREE.Mesh(
      new THREE.SphereGeometry(3400, 32, 16),
      new THREE.ShaderMaterial({
        side: THREE.BackSide,
        depthWrite: false,
        fog: false,
        uniforms: skyU,
        vertexShader: `
          varying vec3 vDir;
          void main() {
            vDir = normalize(position);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }`,
        fragmentShader: `
          uniform vec3 topColor, horizonColor, sunDir, sunColor;
          uniform float sunGlow;
          varying vec3 vDir;
          void main() {
            float h = clamp(vDir.y, 0.0, 1.0);
            vec3 col = mix(horizonColor, topColor, pow(h, 0.5));
            float s = max(dot(normalize(vDir), normalize(sunDir)), 0.0);
            col += sunColor * pow(s, 350.0) * 2.2 * sunGlow;
            col += sunColor * pow(s, 8.0) * 0.40 * sunGlow;
            col += sunColor * pow(s, 2.0) * 0.12 * sunGlow;
            gl_FragColor = vec4(col, 1.0);
          }`,
      })
    );
    scene.add(sky);

    {
      const n = 1100, p = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const v = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 0.9 + 0.12, Math.random() * 2 - 1)
          .normalize().multiplyScalar(3200);
        p.set([v.x, v.y, v.z], i * 3);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(p, 3));
      stars = new THREE.Points(g, new THREE.PointsMaterial({
        color: 0xCFD8FF, size: 3.0, sizeAttenuation: false,
        transparent: true, opacity: 0, depthWrite: false, fog: false,
      }));
      scene.add(stars);
    }

    hemi = new THREE.HemisphereLight(DAY.hemiSky, DAY.hemiGround, DAY.hemiIntensity);
    scene.add(hemi);

    sun = new THREE.DirectionalLight(DAY.sunColor, DAY.sunIntensity);
    sun.position.copy(SUN_DIR_DAY).multiplyScalar(800);
    if (KW.quality.shadows) {
      sun.castShadow = true;
      sun.shadow.mapSize.set(KW.quality.shadowMapSize, KW.quality.shadowMapSize);
      const s = 380;
      sun.shadow.camera.left = -s; sun.shadow.camera.right = s;
      sun.shadow.camera.top = s; sun.shadow.camera.bottom = -s;
      sun.shadow.camera.near = 50; sun.shadow.camera.far = 2000;
      sun.shadow.bias = -0.0004;
      sun.shadow.normalBias = 0.06;
    }
    scene.add(sun);
    scene.add(sun.target);

    const f = KW.quality.fogDay;
    scene.fog = new THREE.Fog(f.color, f.near, f.far);

    buildTerrain();
    buildRiver();
  };

  /**
   * Instanced low-poly-plus trees with clustered canopies.
   * items: [{x, z, s, type}]  type 0=aspen, 1=cottonwood, 2=evergreen
   */
  E.makeTrees = function (items) {
    const groups = [[], [], []];
    for (const it of items) groups[it.type || 0].push(it);

    const builders = [
      function aspen(b) {
        b.add(new THREE.CylinderGeometry(0.09, 0.14, 3.6, 6),
          new THREE.Matrix4().setPosition(0, 1.8, 0), 0xC9C4B4);
        const blobs = [[0, 4.2, 0, 1.5], [0.8, 3.6, 0.3, 1.0], [-0.7, 3.8, -0.3, 0.95], [0.1, 5.1, 0.1, 1.0]];
        for (const [bx, by, bz, br] of blobs) {
          b.add(new THREE.IcosahedronGeometry(br, 1),
            new THREE.Matrix4().setPosition(bx, by, bz),
            new THREE.Color(0x6D9140).offsetHSL(0, 0, (Math.random() - 0.5) * 0.07));
        }
      },
      function cottonwood(b) {
        b.add(new THREE.CylinderGeometry(0.2, 0.34, 5.2, 6),
          new THREE.Matrix4().setPosition(0, 2.6, 0), 0x6B5A44);
        const blobs = [[0, 6.4, 0, 2.6], [1.8, 5.4, 0.6, 1.7], [-1.7, 5.7, -0.5, 1.8], [0.4, 8.0, 0.3, 1.8], [-0.6, 4.6, 1.5, 1.4]];
        for (const [bx, by, bz, br] of blobs) {
          b.add(new THREE.IcosahedronGeometry(br, 1),
            new THREE.Matrix4().setPosition(bx, by, bz),
            new THREE.Color(0x55753A).offsetHSL(0, 0, (Math.random() - 0.5) * 0.08));
        }
      },
      function evergreen(b) {
        b.add(new THREE.CylinderGeometry(0.12, 0.2, 2.2, 6),
          new THREE.Matrix4().setPosition(0, 1.1, 0), 0x5C4A36);
        const tiers = [[2.6, 2.1, 2.6], [4.4, 1.6, 2.3], [6.0, 1.1, 2.0]];
        for (const [ty, tr, th] of tiers) {
          b.add(new THREE.ConeGeometry(tr, th, 8),
            new THREE.Matrix4().setPosition(0, ty, 0),
            new THREE.Color(0x33502E).offsetHSL(0, 0, (Math.random() - 0.5) * 0.05));
        }
      },
    ];

    for (let t = 0; t < 3; t++) {
      if (!groups[t].length) continue;
      const batch = new KW.util.GeoBatch();
      builders[t](batch);
      const geo = batch.merge();
      const mat = new THREE.MeshLambertMaterial({ vertexColors: true });
      const inst = new THREE.InstancedMesh(geo, mat, groups[t].length);
      const m = new THREE.Matrix4();
      const q = new THREE.Quaternion();
      const up = new THREE.Vector3(0, 1, 0);
      groups[t].forEach((it, i) => {
        q.setFromAxisAngle(up, (it.x * 13.7 + it.z * 7.3) % 6.28);
        const s = it.s || 1;
        const y = it.y !== undefined ? it.y : 0;
        m.compose(new THREE.Vector3(it.x, y, it.z), q, new THREE.Vector3(s, s * (0.9 + ((i * 37) % 10) / 40), s));
        inst.setMatrixAt(i, m);
      });
      inst.castShadow = true;
      scene.add(inst);
    }
  };

  // Forest the mountainsides with instanced evergreens placed on the terrain.
  E.forest = function () {
    const items = [];
    const r = KW.util.rng(777);
    for (let i = 0; i < 1400; i++) {
      const x = (r() - 0.5) * 5200, z = (r() - 0.5) * 5200;
      const h = E.terrainHeight(x, z);
      if (h < 25 || h > 620) continue;          // tree line band
      if (x > -460 && x < 420 && z > -720 && z < 200) continue; // not in town
      items.push({ x, z, y: h - 1.2, type: 2, s: 1.6 + r() * 2.2 });
    }
    E.makeTrees(items);
  };

  // ---------------- day / night ----------------
  let targetNight = 0;
  E.toggleNight = function () { targetNight = targetNight > 0.5 ? 0 : 1; };

  const _c = new THREE.Color();
  E.update = function (dt) {
    const t = E.nightT;
    if (Math.abs(t - targetNight) > 0.001) {
      E.nightT = THREE.MathUtils.clamp(t + Math.sign(targetNight - t) * dt / 2.5, 0, 1);
      applyNight(E.nightT);
    }
  };

  function applyNight(t) {
    E.nightT = t;
    skyU.topColor.value.lerpColors(DAY.top, NIGHT.top, t);
    skyU.horizonColor.value.lerpColors(DAY.horizon, NIGHT.horizon, t);
    skyU.sunDir.value.lerpVectors(SUN_DIR_DAY, SUN_DIR_NIGHT, t).normalize();
    skyU.sunGlow.value = 1.0 - t * 0.82;
    skyU.sunColor.value.lerpColors(new THREE.Color(0xFFE9C4), new THREE.Color(0xDFE8FF), t);

    sun.color.lerpColors(DAY.sunColor, NIGHT.sunColor, t);
    sun.intensity = THREE.MathUtils.lerp(DAY.sunIntensity, NIGHT.sunIntensity, t);
    sun.position.lerpVectors(SUN_DIR_DAY, SUN_DIR_NIGHT, t).normalize().multiplyScalar(800);

    hemi.color.lerpColors(DAY.hemiSky, NIGHT.hemiSky, t);
    hemi.groundColor.lerpColors(DAY.hemiGround, NIGHT.hemiGround, t);
    hemi.intensity = THREE.MathUtils.lerp(DAY.hemiIntensity, NIGHT.hemiIntensity, t);

    const fd = KW.quality.fogDay, fn = KW.quality.fogNight;
    scene.fog.color.lerpColors(_c.setHex(fd.color), new THREE.Color(fn.color), t);
    scene.fog.near = THREE.MathUtils.lerp(fd.near, fn.near, t);
    scene.fog.far = THREE.MathUtils.lerp(fd.far, fn.far, t);

    stars.material.opacity = Math.max(0, t - 0.45) / 0.55;

    for (const m of E.emissiveMats) {
      m.emissiveIntensity = (m.userData.dayGlow || 0) + (m.userData.nightGlow - (m.userData.dayGlow || 0)) * t;
    }
    for (const l of E.pointLights) {
      l.intensity = l.userData.dayI + (l.userData.nightI - l.userData.dayI) * t;
    }
    KW.state.night = t > 0.5;
  }

  E.applyNight = applyNight;
  return E;
})();
