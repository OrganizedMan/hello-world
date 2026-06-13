/* Sky, sun, fog, terrain backdrop (Bald Mountain & valley ridges), trees,
 * and the day/night system. */
KW.env = (function () {
  const E = {};
  let sky, sun, moon, hemi, stars, scene;
  let skyU; // sky shader uniforms

  const DAY = {
    top: new THREE.Color(0x7fa8d4),
    horizon: new THREE.Color(0xf6c98e),
    sunColor: new THREE.Color(0xffd9a6),
    sunIntensity: 1.15,
    hemiSky: new THREE.Color(0xbcd2e8),
    hemiGround: new THREE.Color(0x8a7a5a),
    hemiIntensity: 0.55,
  };
  const NIGHT = {
    top: new THREE.Color(0x060a18),
    horizon: new THREE.Color(0x16203a),
    sunColor: new THREE.Color(0x8fa6d4),
    sunIntensity: 0.18,
    hemiSky: new THREE.Color(0x223052),
    hemiGround: new THREE.Color(0x141210),
    hemiIntensity: 0.32,
  };

  const SUN_DIR_DAY = new THREE.Vector3(-0.75, 0.28, -0.35).normalize();  // low in the WNW
  const SUN_DIR_NIGHT = new THREE.Vector3(0.4, 0.55, 0.45).normalize();   // moon from the SE

  E.nightT = 0; // 0 = golden hour, 1 = night
  E.emissiveMats = []; // window glass, lamp heads, lit signs — brighten at night

  E.init = function (sc) {
    scene = sc;

    // --- Sky dome ---
    skyU = {
      topColor: { value: DAY.top.clone() },
      horizonColor: { value: DAY.horizon.clone() },
      sunDir: { value: SUN_DIR_DAY.clone() },
      sunColor: { value: new THREE.Color(0xffe9c4) },
      sunGlow: { value: 1.0 },
    };
    sky = new THREE.Mesh(
      new THREE.SphereGeometry(2400, 32, 16),
      new THREE.ShaderMaterial({
        side: THREE.BackSide,
        depthWrite: false,
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
            vec3 col = mix(horizonColor, topColor, pow(h, 0.55));
            float s = max(dot(normalize(vDir), normalize(sunDir)), 0.0);
            col += sunColor * pow(s, 220.0) * 1.6 * sunGlow;   // sun disc
            col += sunColor * pow(s, 6.0) * 0.35 * sunGlow;    // halo
            gl_FragColor = vec4(col, 1.0);
          }`,
      })
    );
    scene.add(sky);

    // --- Stars (visible at night only) ---
    {
      const n = 900, p = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const v = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 0.9 + 0.12, Math.random() * 2 - 1)
          .normalize().multiplyScalar(2200);
        p.set([v.x, v.y, v.z], i * 3);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(p, 3));
      stars = new THREE.Points(g, new THREE.PointsMaterial({
        color: 0xcfd8ff, size: 3.2, sizeAttenuation: false,
        transparent: true, opacity: 0, depthWrite: false,
      }));
      scene.add(stars);
    }

    // --- Lights ---
    hemi = new THREE.HemisphereLight(DAY.hemiSky, DAY.hemiGround, DAY.hemiIntensity);
    scene.add(hemi);

    sun = new THREE.DirectionalLight(DAY.sunColor, DAY.sunIntensity);
    sun.position.copy(SUN_DIR_DAY).multiplyScalar(700);
    if (KW.quality.shadows) {
      sun.castShadow = true;
      sun.shadow.mapSize.set(KW.quality.shadowMapSize, KW.quality.shadowMapSize);
      const s = 340;
      sun.shadow.camera.left = -s; sun.shadow.camera.right = s;
      sun.shadow.camera.top = s; sun.shadow.camera.bottom = -s;
      sun.shadow.camera.near = 50; sun.shadow.camera.far = 1600;
      sun.shadow.bias = -0.0004;
    }
    scene.add(sun);
    scene.add(sun.target);

    // --- Fog ---
    const f = KW.quality.fogDay;
    scene.fog = new THREE.Fog(f.color, f.near, f.far);

    // --- Valley floor ---
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(5200, 5200),
      new THREE.MeshLambertMaterial({ map: KW.textures.grass() })
    );
    ground.material.map.repeat.set(260, 260);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.25;
    ground.receiveShadow = true;
    scene.add(ground);

    buildMountains();
    buildRiver();
  };

  function ridgeFlat(w, h, segs, jag, texture, peakBias) {
    // A "theater flat" ridge: displaced plane silhouette, fog does the rest.
    const g = new THREE.PlaneGeometry(w, h, segs, 6);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i);
      const tx = x / w + 0.5; // 0..1 across
      // silhouette: smooth humps + noise, optionally one dominant peak
      let crest = Math.sin(tx * Math.PI) * 0.6 + 0.4;
      if (peakBias !== undefined) crest = Math.pow(Math.sin(tx * Math.PI), peakBias);
      crest += (Math.sin(tx * 23.7) * 0.5 + Math.sin(tx * 9.3 + 2)) * jag;
      const ty = y / h + 0.5; // 0 bottom, 1 top
      pos.setY(i, (ty * crest - 0.5) * h);
      pos.setZ(i, Math.sin(tx * 13.1) * w * 0.02 - ty * w * 0.06); // lean back
    }
    g.computeVertexNormals();
    const m = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ map: texture }));
    return m;
  }

  function buildMountains() {
    // Bald Mountain — the big one, SW of downtown, ski runs visible.
    const baldy = ridgeFlat(2400, 880, 80, 0.05, KW.textures.baldy(), 0.85);
    baldy.position.set(-1100, 260, 1000);
    baldy.rotation.y = 2.32; // face NE, toward downtown
    scene.add(baldy);

    // Surrounding ridgelines boxing in the valley.
    const rt = KW.textures.ridge();
    const ringDefs = [
      { x: 300, z: -1500, ry: 0, w: 2600, h: 420 },            // north (toward Sun Valley)
      { x: 1400, z: -300, ry: -Math.PI / 2.2, w: 2400, h: 460 }, // east (Knob Hill side)
      { x: 700, z: 1300, ry: Math.PI, w: 2200, h: 380 },         // south (down-valley)
      { x: -1500, z: -700, ry: Math.PI / 2.3, w: 2200, h: 430 }, // northwest
    ];
    for (const d of ringDefs) {
      const m = ridgeFlat(d.w, d.h, 64, 0.10, rt);
      m.position.set(d.x, d.h * 0.22, d.z);
      m.rotation.y = d.ry;
      scene.add(m);
    }
  }

  function buildRiver() {
    // Big Wood River corridor west of town: water ribbon + brushy banks.
    const water = new THREE.Mesh(
      new THREE.PlaneGeometry(26, 2400),
      new THREE.MeshLambertMaterial({ color: 0x39597a })
    );
    water.rotation.x = -Math.PI / 2;
    water.position.set(-330, -0.1, -300);
    scene.add(water);
    E.riverPos = new THREE.Vector3(-330, 0, -300); // audio uses this
  }

  /**
   * Instanced low-poly trees. items: [{x, z, s, type}]  type 0=aspen, 1=cottonwood, 2=evergreen
   */
  E.makeTrees = function (items) {
    const defs = [
      { trunk: [0.10, 0.14, 3.2], trunkCol: 0xc9c4b4, canopy: 'ball', canopyCol: 0x6d9140, cy: 4.0, cr: 1.5 },
      { trunk: [0.22, 0.3, 4.4], trunkCol: 0x6b5a44, canopy: 'ball', canopyCol: 0x5d7c36, cy: 6.0, cr: 3.0 },
      { trunk: [0.14, 0.2, 2.2], trunkCol: 0x5c4a36, canopy: 'cone', canopyCol: 0x33502e, cy: 5.4, cr: 1.9 },
    ];
    const groups = [[], [], []];
    for (const it of items) groups[it.type || 0].push(it);

    for (let t = 0; t < 3; t++) {
      if (!groups[t].length) continue;
      const d = defs[t];
      const batch = new KW.util.GeoBatch();
      const trunkGeo = new THREE.CylinderGeometry(d.trunk[0], d.trunk[1], d.trunk[2], 5);
      const mt = new THREE.Matrix4().setPosition(0, d.trunk[2] / 2, 0);
      batch.add(trunkGeo, mt, d.trunkCol);
      const canGeo = d.canopy === 'cone'
        ? new THREE.ConeGeometry(d.cr, d.cy * 1.3, 7)
        : new THREE.IcosahedronGeometry(d.cr, 1);
      const mc = new THREE.Matrix4().setPosition(0, d.canopy === 'cone' ? d.trunk[2] + d.cy * 0.55 : d.cy, 0);
      batch.add(canGeo, mc, d.canopyCol);
      const geo = batch.merge();
      const mat = new THREE.MeshLambertMaterial({ vertexColors: true });
      const inst = new THREE.InstancedMesh(geo, mat, groups[t].length);
      const m = new THREE.Matrix4();
      const q = new THREE.Quaternion();
      const up = new THREE.Vector3(0, 1, 0);
      groups[t].forEach((it, i) => {
        q.setFromAxisAngle(up, (it.x * 13.7 + it.z * 7.3) % 6.28);
        const s = it.s || 1;
        m.compose(new THREE.Vector3(it.x, 0, it.z), q, new THREE.Vector3(s, s * (0.9 + ((i * 37) % 10) / 40), s));
        inst.setMatrixAt(i, m);
      });
      inst.castShadow = true;
      scene.add(inst);
    }
  };

  // --- Day / night ---
  let targetNight = 0;
  E.toggleNight = function () { targetNight = targetNight > 0.5 ? 0 : 1; };

  const _c = new THREE.Color();
  E.update = function (dt) {
    const t = E.nightT;
    const want = targetNight;
    if (Math.abs(t - want) > 0.001) {
      E.nightT = THREE.MathUtils.clamp(t + Math.sign(want - t) * dt / 2.5, 0, 1);
      applyNight(E.nightT);
    }
  };

  function applyNight(t) {
    skyU.topColor.value.lerpColors(DAY.top, NIGHT.top, t);
    skyU.horizonColor.value.lerpColors(DAY.horizon, NIGHT.horizon, t);
    skyU.sunDir.value.lerpVectors(SUN_DIR_DAY, SUN_DIR_NIGHT, t).normalize();
    skyU.sunGlow.value = 1.0 - t * 0.82; // moon is dimmer
    skyU.sunColor.value.lerpColors(new THREE.Color(0xffe9c4), new THREE.Color(0xdfe8ff), t);

    sun.color.lerpColors(DAY.sunColor, NIGHT.sunColor, t);
    sun.intensity = THREE.MathUtils.lerp(DAY.sunIntensity, NIGHT.sunIntensity, t);
    sun.position.lerpVectors(SUN_DIR_DAY, SUN_DIR_NIGHT, t).normalize().multiplyScalar(700);

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
    KW.state.night = t > 0.5;
  }

  E.applyNight = applyNight;
  return E;
})();
