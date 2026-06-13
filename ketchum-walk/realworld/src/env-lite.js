/* Lightweight environment for the real-world (Google 3D Tiles) build:
 * sky dome, sun/hemisphere lights, fog, stars, day/night blending.
 * The photogrammetry has daylight baked in, so "night" is a blue-hour
 * grade: dim warm-to-blue lights, dark sky, lit windows via emissives. */
KW.env = (function () {
  const E = {};
  let sky, sun, hemi, stars, scene, renderer;
  let skyU;

  const DAY = {
    top: new THREE.Color(0x6F9CC9), horizon: new THREE.Color(0xF4C68F),
    sunColor: new THREE.Color(0xFFD9A6), sunIntensity: 1.6,
    hemiSky: new THREE.Color(0xBCD2E8), hemiGround: new THREE.Color(0x8A7A5A),
    hemiIntensity: 1.45, exposure: 1.1,
  };
  const NIGHT = {
    top: new THREE.Color(0x060A18), horizon: new THREE.Color(0x16203A),
    sunColor: new THREE.Color(0x8FA6D4), sunIntensity: 0.22,
    hemiSky: new THREE.Color(0x223052), hemiGround: new THREE.Color(0x141210),
    hemiIntensity: 0.5, exposure: 0.5,
  };
  const SUN_DIR_DAY = new THREE.Vector3(-0.75, 0.30, -0.35).normalize();
  const SUN_DIR_NIGHT = new THREE.Vector3(0.4, 0.55, 0.45).normalize();

  E.nightT = 0;
  E.emissiveMats = [];
  E.pointLights = [];

  E.init = function (sc, rend) {
    scene = sc; renderer = rend;
    skyU = {
      topColor: { value: DAY.top.clone() },
      horizonColor: { value: DAY.horizon.clone() },
      sunDir: { value: SUN_DIR_DAY.clone() },
      sunColor: { value: new THREE.Color(0xFFE9C4) },
      sunGlow: { value: 1.0 },
    };
    sky = new THREE.Mesh(
      new THREE.SphereGeometry(5200, 32, 16),
      new THREE.ShaderMaterial({
        side: THREE.BackSide, depthWrite: false, fog: false, uniforms: skyU,
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
            gl_FragColor = vec4(col, 1.0);
          }`,
      })
    );
    sky.renderOrder = -10;
    scene.add(sky);

    const n = 1100, p = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const v = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 0.9 + 0.12, Math.random() * 2 - 1)
        .normalize().multiplyScalar(5000);
      p.set([v.x, v.y, v.z], i * 3);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(p, 3));
    stars = new THREE.Points(g, new THREE.PointsMaterial({
      color: 0xCFD8FF, size: 3.0, sizeAttenuation: false,
      transparent: true, opacity: 0, depthWrite: false, fog: false,
    }));
    scene.add(stars);

    hemi = new THREE.HemisphereLight(DAY.hemiSky, DAY.hemiGround, DAY.hemiIntensity);
    scene.add(hemi);
    sun = new THREE.DirectionalLight(DAY.sunColor, DAY.sunIntensity);
    sun.position.copy(SUN_DIR_DAY).multiplyScalar(800);
    scene.add(sun);

    scene.fog = new THREE.Fog(0xE9C69A, 600, 9000);
  };

  let targetNight = 0;
  E.toggleNight = function () { targetNight = targetNight > 0.5 ? 0 : 1; };

  E.update = function (dt) {
    if (Math.abs(E.nightT - targetNight) > 0.001) {
      E.nightT = THREE.MathUtils.clamp(E.nightT + Math.sign(targetNight - E.nightT) * dt / 2.5, 0, 1);
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
    hemi.color.lerpColors(DAY.hemiSky, NIGHT.hemiSky, t);
    hemi.groundColor.lerpColors(DAY.hemiGround, NIGHT.hemiGround, t);
    hemi.intensity = THREE.MathUtils.lerp(DAY.hemiIntensity, NIGHT.hemiIntensity, t);
    renderer.toneMappingExposure = THREE.MathUtils.lerp(DAY.exposure, NIGHT.exposure, t);
    scene.fog.color.lerpColors(new THREE.Color(0xE9C69A), new THREE.Color(0x0A1020), t);
    scene.fog.near = THREE.MathUtils.lerp(600, 200, t);
    scene.fog.far = THREE.MathUtils.lerp(9000, 2600, t);
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
