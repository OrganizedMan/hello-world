/* Grumpy's interior for the real-world build.
 * The photogrammetry building can't be hollowed out, so stepping through
 * the door teleports you into a hand-built interior "pocket" placed far
 * from the play area; stepping back out returns you to the street. */
KW.grumpysInterior = (function () {
  const GI = {};
  const PX = 5000, PZ = 5000;   // pocket center, well away from the tiles
  const W = 16, D = 12, H = 4.2, WALL = 0.3;
  let exitSpot = null;          // where to return the player

  GI.build = function (scene, colliders, interactables, onEnterExit) {
    const T = KW.textures;
    const front = PZ - D / 2, back = PZ + D / 2;
    const batch = new KW.util.GeoBatch();
    const bx = (w, h, d, x, y, z, c) => batch.box(w, h, d, x, y, z, c);

    // shell: floor, ceiling, four walls (door is a teleport, not a gap)
    const fl = T.woodFloor();
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(W, D),
      new THREE.MeshPhongMaterial({ map: fl.map, bumpMap: fl.bumpMap, bumpScale: 0.02, shininess: 30, specular: 0x443322 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(PX, 0.0, PZ);
    floor.material.map.repeat.set(4, 3);
    floor.material.bumpMap.repeat.set(4, 3);
    scene.add(floor);
    const ceil = new THREE.Mesh(new THREE.PlaneGeometry(W, D),
      new THREE.MeshLambertMaterial({ color: 0x2E2520 }));
    ceil.rotation.x = Math.PI / 2;
    ceil.position.set(PX, H - 0.4, PZ);
    scene.add(ceil);

    // walls — red-painted boards, license plates, wainscot
    bx(W, H, WALL, PX, H / 2, front, 0x8A4434);
    bx(W, H, WALL, PX, H / 2, back, 0x8A4434);
    bx(WALL, H, D, PX - W / 2, H / 2, PZ, 0x84402F);
    bx(WALL, H, D, PX + W / 2, H / 2, PZ, 0x84402F);
    colliders.push(
      { minX: PX - W / 2, maxX: PX + W / 2, minZ: front - 0.4, maxZ: front + 0.2 },
      { minX: PX - W / 2, maxX: PX + W / 2, minZ: back - 0.2, maxZ: back + 0.4 },
      { minX: PX - W / 2 - 0.2, maxX: PX - W / 2 + 0.2, minZ: front, maxZ: back },
      { minX: PX + W / 2 - 0.2, maxX: PX + W / 2 + 0.2, minZ: front, maxZ: back },
    );
    bx(W - 0.4, 1.2, 0.1, PX, 0.66, back - WALL / 2 - 0.08, 0x4E3A26);
    // door (visual) on the front wall
    bx(1.3, 2.3, 0.12, PX + 3, 1.15, front + WALL / 2 + 0.05, 0x5C3A22);
    bx(0.1, 0.1, 0.1, PX + 3.5, 1.1, front + WALL / 2 + 0.13, 0xC9B23C); // knob
    // front window with daylight glow
    const winMat = new THREE.MeshLambertMaterial({ color: 0xEAD9B0, emissive: 0xFFE8B8, emissiveIntensity: 0.9 });
    winMat.userData = { dayGlow: 0.9, nightGlow: 0.06 };
    KW.env.emissiveMats.push(winMat);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 1.5), winMat);
    win.position.set(PX - 4.2, 1.9, front + WALL / 2 + 0.02);
    scene.add(win);
    bx(3.7, 0.12, 0.16, PX - 4.2, 2.72, front + WALL / 2 + 0.04, 0xF2EAD8);
    bx(3.7, 0.12, 0.16, PX - 4.2, 1.08, front + WALL / 2 + 0.04, 0xF2EAD8);

    // ---- bar along the back wall ----
    const barZ = back - 1.9;
    bx(10, 1.12, 0.7, PX - 1, 0.56, barZ, 0x3A2614);
    colliders.push({ minX: PX - 6, maxX: PX + 4, minZ: barZ - 0.45, maxZ: back });
    const top = new THREE.Mesh(new THREE.PlaneGeometry(10.4, 0.95),
      new THREE.MeshPhongMaterial({ map: T.barTop().map, shininess: 70, specular: 0x886644 }));
    top.rotation.x = -Math.PI / 2;
    top.position.set(PX - 1, 1.13, barZ);
    scene.add(top);
    bx(10, 0.12, 0.16, PX - 1, 0.16, barZ - 0.42, 0x8A6D3B);

    // back bar shelving + bottles
    bx(9.6, 0.08, 0.5, PX - 1, 1.5, back - 0.35, 0x4A3017);
    bx(9.6, 0.08, 0.5, PX - 1, 2.1, back - 0.35, 0x4A3017);
    const r = KW.util.rng(99);
    const bottleCols = [0x3A6E2A, 0x6E3A1A, 0x2A3A6E, 0xC8A23C, 0x842A2A, 0x4A4A4A];
    for (let shelf = 0; shelf < 2; shelf++) {
      for (let i = 0; i < 16; i++) {
        const px = PX - 5.4 + i * 0.58 + r() * 0.12;
        const g = new THREE.CylinderGeometry(0.05, 0.06, 0.32, 6);
        batch.add(g, new THREE.Matrix4().setPosition(px, 1.54 + shelf * 0.6 + 0.16, back - 0.35),
          bottleCols[(i * 5 + shelf) % bottleCols.length]);
      }
    }
    // taps + trough
    for (let i = 0; i < 4; i++) {
      bx(0.06, 0.34, 0.06, PX - 2.4 + i * 0.5, 1.36, barZ - 0.1, 0xC9C4B4);
      bx(0.1, 0.08, 0.1, PX - 2.4 + i * 0.5, 1.56, barZ - 0.1, 0x8A2A22);
    }
    bx(2.4, 0.3, 0.3, PX - 1.65, 1.18, barZ - 0.1, 0x2A2A2E);
    // stools
    for (let i = 0; i < 5; i++) {
      const sx = PX - 5 + i * 2;
      batch.add(new THREE.CylinderGeometry(0.24, 0.24, 0.08, 10),
        new THREE.Matrix4().setPosition(sx, 0.78, barZ - 1.0), 0x6E2F28);
      batch.add(new THREE.CylinderGeometry(0.04, 0.05, 0.76, 8),
        new THREE.Matrix4().setPosition(sx, 0.39, barZ - 1.0), 0x222222);
    }
    // license plates / photos
    for (let i = 0; i < 7; i++) {
      bx(0.42, 0.22, 0.03, PX - 5.5 + i * 1.4 + r() * 0.5, 2.6 + r() * 0.8, back - WALL / 2 - 0.05,
        [0xC8B43C, 0x8A9AB0, 0xB05C47, 0xD8D2C4][i % 4]);
    }
    const merged = new THREE.Mesh(batch.merge(), new THREE.MeshLambertMaterial({ vertexColors: true }));
    scene.add(merged);

    // communal picnic tables
    KW.props.begin();
    KW.props.picnicTable(PX - 4, PZ - 2.2, 0.04);
    KW.props.picnicTable(PX + 1.5, PZ - 2.0, -0.06);
    KW.props.flush(scene);
    colliders.push({ minX: PX - 5.3, maxX: PX - 2.7, minZ: PZ - 3.2, maxZ: PZ - 1.2 });
    colliders.push({ minX: PX + 0.2, maxX: PX + 2.8, minZ: PZ - 3.0, maxZ: PZ - 1.0 });

    // TV mid-ballgame + neon + pendant lights
    const tv = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 0.95),
      new THREE.MeshBasicMaterial({ map: T.tvScreen() }));
    tv.position.set(PX + 3.2, 2.75, back - WALL / 2 - 0.12);
    tv.rotation.y = Math.PI;
    scene.add(tv);
    const tvFrame = new THREE.Mesh(new THREE.BoxGeometry(1.84, 1.08, 0.1),
      new THREE.MeshLambertMaterial({ color: 0x111111 }));
    tvFrame.position.set(PX + 3.2, 2.75, back - WALL / 2 - 0.05);
    scene.add(tvFrame);

    const nt = T.sign("GRUMPY'S", 'neon');
    const nm = new THREE.MeshLambertMaterial({ map: nt, emissive: new THREE.Color(0xFF8A5C), emissiveMap: nt });
    nm.userData = { dayGlow: 0.4, nightGlow: 1.0 };
    KW.env.emissiveMats.push(nm);
    const neon = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 0.8), nm);
    neon.position.set(PX - 1, 3.2, back - WALL / 2 - 0.08);
    neon.rotation.y = Math.PI;
    scene.add(neon);

    for (const px of [PX - 3, PX + 1.5]) {
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 6),
        new THREE.MeshLambertMaterial({ color: 0xFFF2CF, emissive: 0xFFDF9A, emissiveIntensity: 0.8 }));
      bulb.position.set(px, 2.7, PZ - 1);
      scene.add(bulb);
      const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, H - 0.4 - 2.7, 4),
        new THREE.MeshLambertMaterial({ color: 0x191512 }));
      cord.position.set(px, (H - 0.4 + 2.7) / 2, PZ - 1);
      scene.add(cord);
      const light = new THREE.PointLight(0xFFD9A0, 14, 11, 1.6);
      light.position.set(px, 2.65, PZ - 1);
      light.userData = { dayI: 14, nightI: 26 }; // physical units in newer three
      KW.env.pointLights.push(light);
      scene.add(light);
    }

    // ---- interactables ----
    interactables.push({
      x: PX - 1, z: barZ - 1.4, r: 2.4,
      label: 'Press E to order a schooner',
      action: 'orderSchooner',
    });
    interactables.push({
      x: PX + 3, z: front + 1.2, r: 1.8,
      label: 'Press E to head back outside',
      onUse: () => {
        if (exitSpot) {
          KW.player.teleport(exitSpot.x, exitSpot.z, exitSpot.yaw, exitSpot.y);
          onEnterExit(false);
        }
      },
    });
  };

  /** Teleport the player inside; remember where they came from. */
  GI.enter = function (fromX, fromY, fromZ, fromYaw) {
    exitSpot = { x: fromX, y: fromY, z: fromZ, yaw: fromYaw };
    KW.player.teleport(PX + 3, PZ - D / 2 + 2.2, Math.PI, 0);
  };
  GI.isInside = function (pos) {
    return Math.abs(pos.x - PX) < W && Math.abs(pos.z - PZ) < D;
  };
  GI.floorY = 0;
  GI.center = { x: PX, z: PZ };

  return GI;
})();
