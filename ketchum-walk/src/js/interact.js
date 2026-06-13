/* Interaction system + the schooner.
 * E — use the nearest interactable (order / pick up)
 * F — take a drink while holding
 * G — set the schooner down where you're standing */
KW.interact = (function () {
  const I = {};
  let camera, scene, promptEl;
  let interactables = [];
  let nearest = null;
  let held = null;       // { group, sips }
  const MAX_SIPS = 6;
  let bobT = 0;

  // ---- schooner model ----
  function makeSchooner() {
    const group = new THREE.Group();
    const pts = [];
    // goblet profile (meters): heavy base, short stem, big bowl
    const profile = [
      [0.0, 0.0], [0.052, 0.0], [0.055, 0.012], [0.024, 0.028], [0.018, 0.05],
      [0.018, 0.085], [0.034, 0.105], [0.058, 0.13], [0.071, 0.175],
      [0.0755, 0.23], [0.074, 0.275], [0.0715, 0.29],
    ];
    for (const [r, y] of profile) pts.push(new THREE.Vector2(r, y));
    const glass = new THREE.Mesh(
      new THREE.LatheGeometry(pts, 20),
      new THREE.MeshPhongMaterial({
        color: 0xC8DCE4, transparent: true, opacity: 0.2,
        shininess: 140, specular: 0xFFFFFF, side: THREE.DoubleSide,
        depthWrite: false,
      })
    );
    glass.renderOrder = 2;
    group.add(glass);

    const beer = new THREE.Mesh(
      new THREE.CylinderGeometry(0.052, 0.044, 0.15, 16),
      new THREE.MeshPhongMaterial({
        color: 0xC2761C, transparent: true, opacity: 0.96,
        emissive: 0x8A5210, emissiveIntensity: 0.55,
      })
    );
    beer.position.y = 0.195;
    group.add(beer);
    group.userData.beer = beer;

    const foam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.062, 0.058, 0.03, 16),
      new THREE.MeshLambertMaterial({ color: 0xF4EAD8 })
    );
    foam.position.y = 0.285;
    group.add(foam);
    group.userData.foam = foam;
    return group;
  }

  function applySips(group, sips) {
    const t = sips / MAX_SIPS;
    const beer = group.userData.beer, foam = group.userData.foam;
    foam.visible = sips === 0;
    beer.visible = sips < MAX_SIPS;
    beer.scale.y = Math.max(0.06, 1 - t);
    beer.position.y = 0.195 - (0.15 * t) / 2;
  }

  I.init = function (cam, sc, list) {
    camera = cam; scene = sc;
    interactables = list;
    promptEl = document.getElementById('prompt');

    document.addEventListener('keydown', (e) => {
      if (!KW.player.locked) return;
      if (e.code === 'KeyE' && nearest) use(nearest);
      if (e.code === 'KeyF' && held && held.sips < MAX_SIPS) {
        held.sips++;
        applySips(held.group, held.sips);
        KW.audio.gulp && KW.audio.gulp();
      }
      if (e.code === 'KeyG' && held) setDown();
    });
  };

  function use(it) {
    if (typeof it.onUse === 'function') { it.onUse(it); return; }
    if (it.action === 'orderSchooner') {
      if (held) return; // one at a time — house rules
      pickUp(makeSchooner(), 0);
      KW.audio.pour && KW.audio.pour();
    } else if (it.action === 'pickupSchooner') {
      const idx = interactables.indexOf(it);
      if (idx >= 0) interactables.splice(idx, 1);
      scene.remove(it.mesh);
      pickUp(it.mesh, it.sips);
    }
  }

  function pickUp(group, sips) {
    group.position.set(0.34, -0.42, -0.72);
    group.rotation.set(0.06, 0, 0.02);
    group.scale.set(1, 1, 1);
    camera.add(group);
    held = { group, sips };
    applySips(group, sips);
  }

  function setDown() {
    const group = held.group;
    camera.remove(group);
    const yaw = KW.player.getYaw();
    const px = KW.player.position.x - Math.sin(yaw) * 0.9;
    const pz = KW.player.position.z - Math.cos(yaw) * 0.9;
    group.position.set(px, 0.13, pz); // on the ground (or curb) at your feet
    group.rotation.set(0, yaw, 0);
    scene.add(group);
    interactables.push({
      x: px, z: pz, r: 1.6,
      label: held.sips >= MAX_SIPS ? 'Press E to pick up your empty schooner' : 'Press E to pick up your schooner',
      action: 'pickupSchooner', mesh: group, sips: held.sips,
    });
    held = null;
  }

  I.update = function (dt, playerPos) {
    // nearest interactable
    nearest = null;
    let bestD = 1e9;
    for (const it of interactables) {
      const d = Math.hypot(playerPos.x - it.x, playerPos.z - it.z);
      if (d < it.r && d < bestD) { bestD = d; nearest = it; }
    }
    let text = '';
    if (nearest && !(nearest.action === 'orderSchooner' && held)) text = nearest.label;
    else if (held) {
      text = held.sips >= MAX_SIPS ? 'Empty… · G — set it down' : 'F — take a drink · G — set it down';
    }
    if (promptEl.textContent !== text) {
      promptEl.textContent = text;
      promptEl.classList.toggle('visible', !!text);
    }

    // beer sway while walking
    if (held) {
      bobT += dt * (1 + (KW.player.speed || 0) * 1.6);
      const amp = 0.006 + Math.min((KW.player.speed || 0) / 8, 1) * 0.012;
      held.group.position.y = -0.42 + Math.sin(bobT * 2.1) * amp;
      held.group.rotation.z = 0.02 + Math.sin(bobT * 1.05) * amp * 1.8;
    }
  };

  return I;
})();
