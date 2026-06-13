/* Bootstrap: renderer, district construction, game loop, HUD. */
(function () {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, KW.quality.pixelRatioCap));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  if (KW.quality.shadows) {
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }
  document.body.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.08, 7000);
  scene.add(camera); // so the carried schooner renders

  KW.env.init(scene);

  // Build all registered districts (expansion packs register themselves
  // before this file runs — see config.js).
  const ctx = { scene, colliders: [], plaques: [], trees: [], interactables: [] };
  let bounds = null, spawn = null, mainDistrict = null;
  for (const d of KW.districts) {
    d.build(ctx);
    if (!mainDistrict) { mainDistrict = d; spawn = d.spawn; bounds = { ...d.bounds }; }
    else {
      bounds.minX = Math.min(bounds.minX, d.bounds.minX);
      bounds.maxX = Math.max(bounds.maxX, d.bounds.maxX);
      bounds.minZ = Math.min(bounds.minZ, d.bounds.minZ);
      bounds.maxZ = Math.max(bounds.maxZ, d.bounds.maxZ);
    }
  }
  KW.env.makeTrees(ctx.trees);
  KW.env.forest();
  KW.debug = ctx; // console access for development / future sessions

  KW.player.init(camera, renderer.domElement, spawn, bounds, ctx.colliders);
  KW.plaques.init(ctx.plaques);
  KW.interact.init(camera, scene, ctx.interactables);
  KW.minimap.init(mainDistrict, ctx.colliders, ctx.plaques);

  // intro overlay → pointer lock + audio
  const intro = document.getElementById('intro');
  intro.addEventListener('click', () => {
    KW.audio.start();
    KW.player.lock();
  });
  document.addEventListener('pointerlockchange', () => {
    intro.style.display = document.pointerLockElement === renderer.domElement ? 'none' : 'flex';
  });
  // some browsers need a beat between unlock and re-lock; clicking the
  // overlay again handles it.

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  // nearest-intersection HUD label
  const streetEl = document.getElementById('street');
  let lastLabel = '';
  function updateLocation(pos) {
    let av = null, st = null, dAv = 1e9, dSt = 1e9;
    for (const a of mainDistrict.avenues) {
      const d = Math.abs(pos.x - a.x);
      if (d < dAv) { dAv = d; av = a; }
    }
    for (const s of mainDistrict.streets) {
      const d = Math.abs(pos.z - s.z);
      if (d < dSt) { dSt = d; st = s; }
    }
    const label = av && st ? `${av.name} & ${st.name}` : '';
    if (label !== lastLabel) { lastLabel = label; streetEl.textContent = label; }
  }

  const clock = new THREE.Clock();
  let frame = 0;
  function loop() {
    requestAnimationFrame(loop);
    const dt = Math.min(clock.getDelta(), 0.05);
    KW.player.update(dt);
    KW.env.update(dt);
    KW.interact.update(dt, KW.player.position);
    if ((frame++ & 7) === 0) {
      KW.plaques.update(KW.player.position);
      KW.audio.update(KW.player.position);
      updateLocation(KW.player.position);
    }
    KW.minimap.draw(KW.player.position, KW.player.getYaw());
    renderer.render(scene, camera);
  }
  loop();
})();
