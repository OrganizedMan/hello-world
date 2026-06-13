/* First-person controls: pointer lock, WASD + shift jog, head-bob,
 * circle-vs-AABB collision with slide. */
KW.player = (function () {
  const PL = {};
  const keys = {};
  let yaw = Math.PI, pitch = 0;
  let camera, dom;
  const pos = new THREE.Vector3(0, 0, -30);
  const vel = new THREE.Vector3();
  let bobPhase = 0, bobAmp = 0;
  const EYE = 1.68, RADIUS = 0.45;
  const WALK = 4.2, JOG = 7.6;
  let bounds = { minX: -1e9, maxX: 1e9, minZ: -1e9, maxZ: 1e9 };
  let colliders = [];

  PL.locked = false;
  PL.position = pos;
  PL.getYaw = () => yaw;
  PL.setYaw = (v) => { yaw = v; };

  PL.init = function (cam, domElement, spawn, b, cols) {
    camera = cam; dom = domElement;
    bounds = b; colliders = cols;
    pos.set(spawn.x, 0, spawn.z);
    yaw = spawn.yaw || 0;

    document.addEventListener('keydown', (e) => {
      keys[e.code] = true;
      if (e.code === 'KeyN') KW.env.toggleNight();
      if (e.code === 'KeyM') KW.minimap.toggle();
    });
    document.addEventListener('keyup', (e) => { keys[e.code] = false; });

    document.addEventListener('mousemove', (e) => {
      if (!PL.locked) return;
      yaw -= e.movementX * 0.0022;
      pitch -= e.movementY * 0.0022;
      pitch = Math.max(-1.45, Math.min(1.45, pitch));
    });
    document.addEventListener('pointerlockchange', () => {
      PL.locked = document.pointerLockElement === dom;
    });
  };

  PL.lock = function () { dom.requestPointerLock(); };

  PL.update = function (dt) {
    const fwd = (keys.KeyW || keys.ArrowUp ? 1 : 0) - (keys.KeyS || keys.ArrowDown ? 1 : 0);
    const str = (keys.KeyD || keys.ArrowRight ? 1 : 0) - (keys.KeyA || keys.ArrowLeft ? 1 : 0);
    const speed = (keys.ShiftLeft || keys.ShiftRight) ? JOG : WALK;

    const sin = Math.sin(yaw), cos = Math.cos(yaw);
    // forward in look direction (XZ), strafe perpendicular
    const ax = (-sin * fwd + cos * str);
    const az = (-cos * fwd - sin * str);
    const len = Math.hypot(ax, az) || 1;
    const tx = (ax / len) * speed * (fwd || str ? 1 : 0);
    const tz = (az / len) * speed * (fwd || str ? 1 : 0);

    // smooth accel
    vel.x += (tx - vel.x) * Math.min(1, dt * 10);
    vel.z += (tz - vel.z) * Math.min(1, dt * 10);

    let nx = pos.x + vel.x * dt;
    let nz = pos.z + vel.z * dt;

    // collide: resolve each axis separately for sliding
    nx = collideAxis(nx, pos.z, true) ? pos.x : nx;
    nz = collideAxis(nx, nz, false) ? pos.z : nz;

    pos.x = Math.max(bounds.minX, Math.min(bounds.maxX, nx));
    pos.z = Math.max(bounds.minZ, Math.min(bounds.maxZ, nz));

    // head bob
    const moving = Math.hypot(vel.x, vel.z);
    bobAmp += ((moving > 0.4 ? Math.min(moving / WALK, 1.6) : 0) - bobAmp) * Math.min(1, dt * 6);
    bobPhase += dt * moving * 1.9;
    const bobY = Math.sin(bobPhase * 2) * 0.035 * bobAmp;
    const bobX = Math.cos(bobPhase) * 0.02 * bobAmp;

    camera.position.set(pos.x + bobX * cos, EYE + bobY, pos.z - bobX * sin);
    camera.rotation.order = 'YXZ';
    camera.rotation.y = yaw;
    camera.rotation.x = pitch;

    PL.speed = moving;
  };

  function collideAxis(x, z, isX) {
    for (const c of colliders) {
      if (x > c.minX - RADIUS && x < c.maxX + RADIUS &&
          z > c.minZ - RADIUS && z < c.maxZ + RADIUS) return true;
    }
    return false;
  }

  return PL;
})();
