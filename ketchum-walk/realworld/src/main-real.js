/* Real-world Ketchum: streams Google Photorealistic 3D Tiles and runs the
 * walking sim on top — terrain-following, mesh collision, landmark
 * plaques at true coordinates, and Grumpy's interior with the schooner. */
import { TilesRenderer } from '3d-tiles-renderer';
import {
  GoogleCloudAuthPlugin,
  GLTFExtensionsPlugin,
  TileCompressionPlugin,
  TilesFadePlugin,
  ReorientationPlugin,
  EnforceNonZeroErrorPlugin,
} from '3d-tiles-renderer/plugins';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';

(function () {
  const THREE = window.THREE;
  const P = KW.places;
  const $ = (id) => document.getElementById(id);

  // ---------- API key handling ----------
  const params = new URLSearchParams(location.search);
  const DEBUG = params.has('debug');
  // localStorage throws in sandboxed viewers (iOS Files preview) — never let it kill the app
  const lsGet = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* no persistence */ } };
  let apiKey = params.get('key') || lsGet('kw_google_key') || '';
  const keyInput = $('apikey');
  keyInput.value = apiKey;

  // ---------- renderer / scene ----------
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  document.body.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 30000);
  scene.add(camera); // the carried schooner is a camera child

  KW.env.init(scene, renderer);
  document.body.classList.add('realworld');
  for (const b of document.querySelectorAll('#flyui .tb')) {
    const set = (v) => (e) => { e.preventDefault(); e.stopPropagation(); KW.player.fly = v; };
    for (const ev of ['touchstart', 'pointerdown']) b.addEventListener(ev, set(+b.dataset.fly), { passive: false });
    for (const ev of ['touchend', 'touchcancel', 'pointerup', 'pointerleave']) b.addEventListener(ev, set(0), { passive: false });
  }

  // ---------- tiles ----------
  let tiles = null;
  let rootLoaded = false;
  let rootLoadedAt = 0;
  let tileErrs = 0, firstTileErr = '';
  const errEl = $('tileerror');
  function showError(msg) {
    errEl.innerHTML = msg;
    errEl.style.display = 'block';
  }
  window.addEventListener('error', (e) => {
    showError('<b>Something went wrong.</b><br><small>' + (e.message || 'unknown error') + '</small>');
  });
  window.addEventListener('unhandledrejection', (e) => {
    const m = e.reason && (e.reason.message || String(e.reason));
    showError('<b>Something went wrong.</b><br><small>' + m + '</small>');
  });

  function startTiles(key) {
    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.7/');

    tiles = new TilesRenderer();
    tiles.registerPlugin(new GoogleCloudAuthPlugin({ apiToken: key, autoRefreshToken: true }));
    // Google tilesets contain zero-geometric-error tiles that halt LOD
    // refinement (symptom: coarse blobs, "100%", nothing downloading).
    tiles.registerPlugin(new EnforceNonZeroErrorPlugin());
    tiles.registerPlugin(new GLTFExtensionsPlugin({ dracoLoader }));
    tiles.registerPlugin(new TileCompressionPlugin());
    tiles.registerPlugin(new TilesFadePlugin());
    tiles.registerPlugin(new ReorientationPlugin({
      lat: P.ORIGIN.lat * THREE.MathUtils.DEG2RAD,
      lon: P.ORIGIN.lon * THREE.MathUtils.DEG2RAD,
      // Ketchum is ~1765 m above the WGS84 ellipsoid; anchor the origin at
      // street level so the scene (sky, fog, spawn) is sane. The ground
      // raycast below absorbs the remaining offset.
      height: 1765,
      recenter: true,
    }));
    tiles.setCamera(camera);
    tiles.setResolutionFromRenderer(camera, renderer);
    const mobile = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    tiles.errorTarget = mobile ? 10 : 6;
    // min/max must stay ordered: loading halts at max, but eviction only
    // frees memory above min — min > max deadlocks the streamer.
    tiles.lruCache.minBytesSize = (mobile ? 0.15 : 0.3) * 1024 * 1024 * 1024;
    tiles.lruCache.maxBytesSize = (mobile ? 0.3 : 0.5) * 1024 * 1024 * 1024;

    tiles.addEventListener('load-tile-set', () => { rootLoaded = true; rootLoadedAt = performance.now(); errEl.style.display = 'none'; });
    tiles.addEventListener('load-error', (e) => {
      const msg = (e.error && (e.error.message || e.error.toString())) || 'unknown error';
      tileErrs++;
      if (!firstTileErr) firstTileErr = msg;
      if (/40[13]/.test(msg)) {
        showError('<b>Google rejected the API key.</b><br>Check that the key is valid and the <i>Map Tiles API</i> is enabled for it in Google Cloud Console, then reload.<br><small>' + msg + '</small>');
      } else if (!rootLoaded) {
        showError('<b>Could not load the world tiles.</b><br>Check your internet connection and API key, then reload.<br><small>' + msg + '</small>');
      }
    });
    scene.add(tiles.group);
  }

  // ---------- world dressing: landmark beacons + markers ----------
  const ctx = { colliders: [], plaques: [], interactables: [] };
  const beaconMat = new THREE.MeshBasicMaterial({ color: 0xFFC766, transparent: true, opacity: 0.35, depthWrite: false });
  const markers = new THREE.Group();
  scene.add(markers);
  function addBeacon(x, z) {
    const b = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.55, 60, 10, 1, true), beaconMat);
    b.position.set(x, 30, z);
    b.userData.isBeacon = true;
    markers.add(b);
  }
  for (const lm of P.LANDMARKS) {
    const { x, z } = P.toLocal(lm.lat, lm.lon);
    ctx.plaques.push({ x, z, title: lm.title, text: lm.text });
    addBeacon(x, z);
  }

  // Grumpy's: entry interactable + interior pocket
  const GR = P.toLocal(P.GRUMPYS.lat, P.GRUMPYS.lon);
  let insideGrumpys = false;
  addBeacon(GR.x, GR.z);
  ctx.plaques.push({
    x: GR.x, z: GR.z, title: "Grumpy's",
    text: 'No sign out front for years and it never mattered — everyone knows Grumpy\'s. Burgers in plastic baskets, peanut shells underfoot, and the famous schooner: a 32-ounce goblet of cold beer that is basically the town trophy.',
  });
  ctx.interactables.push({
    x: GR.x, z: GR.z, r: 9,
    label: "Press E to step inside Grumpy's",
    onUse: () => {
      const p = KW.player.position;
      setInside(true);
      KW.grumpysInterior.enter(p.x, p.y, p.z, KW.player.getYaw());
    },
  });
  KW.grumpysInterior.build(scene, ctx.colliders, ctx.interactables, setInside);
  function setInside(v) {
    insideGrumpys = v;
    if (tiles) tiles.group.visible = !v;
    markers.visible = !v;
    const c = KW.grumpysInterior.center;
    KW.player.setBounds(v
      ? { minX: c.x - 60, maxX: c.x + 60, minZ: c.z - 60, maxZ: c.z + 60 }
      : BOUNDS);
  }

  // ---------- player ----------
  const BOUNDS = { minX: -1500, maxX: 1500, minZ: -1500, maxZ: 1500 };
  KW.player.init(camera, renderer.domElement, { x: 0, z: 0, yaw: -0.45 }, BOUNDS, ctx.colliders);

  // terrain follow + mesh collision via raycasts into the tile geometry
  const ray = new THREE.Raycaster();
  ray.firstHitOnly = true;
  const DOWN = new THREE.Vector3(0, -1, 0);
  let lastGround = null;
  let groundSettled = false; // true once the tileset has finished its first load
  // Sweep the full column (slow but exhaustive) and latch the topmost surface.
  function sweepTall(x, z) {
    ray.set(new THREE.Vector3(x, 3000, z), DOWN);
    ray.far = 8000;
    const hits = ray.intersectObject(tiles.group, true);
    if (hits.length) {
      lastGround = hits[0].point.y;
      $('loading').style.display = 'none';
    }
  }
  KW.player.groundFn = (x, z) => {
    if (insideGrumpys) return KW.grumpysInterior.floorY;
    if (!tiles || !rootLoaded) return lastGround;
    // Spawn is anchored at an estimated street height, but the streamed
    // surface can be hundreds of meters off — and near downtown, the first
    // coarse tiles to arrive sit well *above* the true street (the valley is
    // ringed by mountains the low-LOD mesh smooths over). So keep sweeping the
    // full column, taking the topmost hit, until the tileset has finished its
    // initial load. Latching the first hit would strand the player in the air
    // because the cheap follow-ray below can't reach back down to street level
    // once the coarse tile is replaced by detail.
    if (!groundSettled) {
      sweepTall(x, z);
      // Settle once the tileset reports a full load — or, if this renderer
      // build doesn't expose loadProgress, after a grace period so we never
      // sweep the whole column forever.
      const loaded = tiles.loadProgress >= 1 || performance.now() - rootLoadedAt > 12000;
      if (loaded && lastGround !== null) groundSettled = true;
      return lastGround;
    }
    // Settled: a cheap short ray that follows the ground we already know.
    ray.set(new THREE.Vector3(x, lastGround + 60, z), DOWN);
    ray.far = 200;
    const hits = ray.intersectObject(tiles.group, true);
    if (hits.length) lastGround = hits[0].point.y;
    // Missed entirely — the surface dropped out of the window (a cliff edge, or
    // a stale latch). Recover with a full sweep instead of floating on the old
    // value.
    else sweepTall(x, z);
    return lastGround;
  };
  // Recovery sweep: if tile geometry is above the camera, we are under the
  // world (whatever the cause) — snap to the topmost surface at our x/z.
  const UP = new THREE.Vector3(0, 1, 0);
  setInterval(() => {
    if (!tiles || !rootLoaded || insideGrumpys) return;
    const p2 = KW.player.position;
    ray.set(new THREE.Vector3(p2.x, p2.y + 1.7, p2.z), UP);
    ray.far = 2500;
    if (ray.intersectObject(tiles.group, true).length) {
      ray.set(new THREE.Vector3(p2.x, 8000, p2.z), DOWN);
      ray.far = 16000;
      const hits = ray.intersectObject(tiles.group, true);
      if (hits.length) {
        lastGround = hits[0].point.y;
        p2.y = lastGround;
        $('loading').style.display = 'none';
      }
    }
  }, 2500);

  const fwd = new THREE.Vector3();
  KW.player.blockFn = (pos, nx, nz) => {
    if (insideGrumpys || !tiles || !rootLoaded || lastGround === null) return false;
    fwd.set(nx - pos.x, 0, nz - pos.z);
    const len = fwd.length();
    if (len < 1e-5) return false;
    fwd.normalize();
    ray.set(new THREE.Vector3(pos.x, pos.y + 1.25, pos.z), fwd);
    ray.far = 0.7;
    const hits = ray.intersectObject(tiles.group, true);
    // allow walking up gentle slopes — only block near-vertical surfaces
    return hits.length > 0 && Math.abs(hits[0].face ? hits[0].face.normal.y : 0) < 0.6;
  };

  KW.plaques.init(ctx.plaques);
  KW.interact.init(camera, scene, ctx.interactables);
  KW.minimap.init(
    { bounds: { minX: -900, maxX: 900, minZ: -900, maxZ: 900 }, streets: [], avenues: [] },
    [], ctx.plaques
  );

  // ---------- intro / pointer lock ----------
  const intro = $('intro');
  let started = false;
  const startGame = () => {
    const key = keyInput.value.trim();
    if (!key) { keyInput.focus(); keyInput.style.borderColor = '#ff6a4a'; return; }
    lsSet('kw_google_key', key);
    if (!tiles) {
      apiKey = key;
      startTiles(key);
      $('loading').style.display = 'block';
    }
    KW.audio.start();
    KW.player.lock();
    if (KW.player.isTouch) intro.style.display = 'none';
    started = true;
  };
  $('startbtn').addEventListener('click', startGame);
  // iOS: divs don't always synthesize clicks — handle the touch directly
  $('startbtn').addEventListener('touchend', (e) => {
    e.preventDefault();
    if (!started || intro.style.display !== 'none') startGame();
  }, { passive: false });
  for (const b of document.querySelectorAll('#touchui .tb')) {
    b.addEventListener('touchstart', (e) => {
      e.preventDefault(); e.stopPropagation();
      document.dispatchEvent(new KeyboardEvent('keydown', { code: b.dataset.k }));
    }, { passive: false });
  }
  keyInput.addEventListener('click', (e) => e.stopPropagation());
  document.addEventListener('pointerlockchange', () => {
    intro.style.display = document.pointerLockElement === renderer.domElement ? 'none' : 'flex';
  });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    if (tiles) tiles.setResolutionFromRenderer(camera, renderer);
  });

  // ---------- HUD: nearest landmark + optional debug coords ----------
  const streetEl = $('street');
  function updateLocation(pos) {
    let best = null, bestD = 1e9;
    for (const pl of ctx.plaques) {
      const d = Math.hypot(pos.x - pl.x, pos.z - pl.z);
      if (d < bestD) { bestD = d; best = pl; }
    }
    let label = insideGrumpys ? "Inside Grumpy's"
      : (best && bestD < 400 ? `${best.title} · ${Math.round(bestD)} m` : 'Ketchum, Idaho');
    if (DEBUG) {
      const g = P.toGeo(pos.x, pos.z);
      label += ` · ${g.lat.toFixed(5)}, ${g.lon.toFixed(5)}`;
    }
    if (streetEl.textContent !== label) streetEl.textContent = label;
  }

  KW.debug = { ctx, scene, get tiles() { return tiles; } };

  // always-on one-line diagnostics (tiny, bottom-left)
  const dbg = document.createElement('div');
  dbg.style.cssText = 'position:fixed;left:8px;bottom:4px;font:10px Menlo,monospace;color:rgba(255,255,255,0.55);z-index:30;text-shadow:0 1px 2px #000;pointer-events:none';
  document.body.appendChild(dbg);

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
      let st = '';
      try {
        if (tiles && tiles.stats) {
          st = ' · dl ' + tiles.stats.downloading + ' parse ' + tiles.stats.parsing
            + ' vis ' + tiles.stats.visible + ' fail ' + tiles.stats.failed
            + ' cache ' + (tiles.lruCache.cachedBytes / 1048576 | 0) + 'MB';
        }
        if (tiles && tiles.loadProgress !== undefined) st += ' · ' + Math.round(tiles.loadProgress * 100) + '%';
      } catch (err) { /* older API */ }
      dbg.textContent = (window.KW_BUILD ? window.KW_BUILD.slice(6, 22) + ' · ' : '')
        + 'y ' + KW.player.position.y.toFixed(1)
        + ' · gnd ' + (lastGround === null ? 'none' : lastGround.toFixed(1))
        + ' · tris ' + (renderer.info.render.triangles / 1000 | 0) + 'k'
        + st
        + (tileErrs ? ' · ERR ' + tileErrs + ' ' + firstTileErr.slice(0, 60) : '');
    }
    if (tiles) {
      camera.updateMatrixWorld();
      tiles.update();
    }
    KW.minimap.draw(KW.player.position, KW.player.getYaw());
    renderer.render(scene, camera);
  }
  loop();
})();
