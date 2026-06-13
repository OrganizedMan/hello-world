/* DISTRICT: Grumpy's — the beloved burger-and-beer dive on Warm Springs Rd
 * (compressed a few blocks closer to downtown than real life so it's an
 * easy walk). Demonstrates the expansion-pack API: registers after
 * downtown, extends the walkable bounds west, and adds the game's first
 * enterable interior plus the schooner interaction. */
(function () {
  const G = KW.grid;
  const P = G.PITCH;
  const ROAD_Z = -5 * P;           // Warm Springs Rd continues west from Sun Valley Rd
  const BX = -310, BZ = ROAD_Z + 26; // building center
  const W = 16, D = 12, H = 4.6;     // exterior shell
  const WALL = 0.3;
  const DOOR_X = BX + 3, DOOR_W = 1.5; // door on the north (road-facing) wall

  function buildShell(scene, colliders) {
    const B = KW.buildings;
    const reg = B.registry();
    const signs = [];
    const red = reg.batches.clap_red;
    const trim = reg.batches.trim;
    const TRIM_C = new THREE.Color(0xF2EAD8);
    const box = (batch, w, h, d, x, y, z, c) => {
      const g = new THREE.BoxGeometry(w, h, d);
      batch.add(g, new THREE.Matrix4().setPosition(x, y, z), c || 0xFFFFFF,
        [Math.max(w, d) * 0.32, h * 0.32]);
    };
    const solid = (w, h, d, x, y, z) => {
      box(red, w, h, d, x, y, z);
      colliders.push({ minX: x - w / 2, maxX: x + w / 2, minZ: z - d / 2, maxZ: z + d / 2 });
    };

    const front = BZ - D / 2, back = BZ + D / 2;
    // north wall with door gap + window
    const leftW = (DOOR_X - DOOR_W / 2) - (BX - W / 2);
    const rightW = (BX + W / 2) - (DOOR_X + DOOR_W / 2);
    solid(leftW, H, WALL, BX - W / 2 + leftW / 2, H / 2, front);
    solid(rightW, H, WALL, DOOR_X + DOOR_W / 2 + rightW / 2, H / 2, front);
    box(red, DOOR_W + 0.4, H - 2.5, WALL, DOOR_X, 2.5 + (H - 2.5) / 2, front); // header above door
    // other three walls
    solid(W, H, WALL, BX, H / 2, back);
    solid(WALL, H, D - WALL, BX - W / 2, H / 2, BZ);
    solid(WALL, H, D - WALL, BX + W / 2, H / 2, BZ);

    // false front + cornice
    box(red, W + 0.4, 1.8, 0.45, BX, H + 0.8, front - 0.1);
    box(trim, W + 0.8, 0.3, 0.7, BX, H + 1.75, front - 0.1, TRIM_C);
    // shed metal roof
    const roof = new THREE.BoxGeometry(W + 1.2, 0.16, D + 1.6);
    roof.applyMatrix4(new THREE.Matrix4().makeRotationX(0.1));
    reg.batches.roof_metal_red.add(roof, new THREE.Matrix4().setPosition(BX, H + 0.25, BZ + 0.3), 0xFFFFFF, [5, 4]);
    // front window (lit) + frame, porch posts and rail
    box(reg.batches.glassLit, 3.4, 1.5, 0.1, BX - 4.2, 1.9, front - 0.06);
    box(trim, 3.7, 0.14, 0.22, BX - 4.2, 2.72, front - 0.1, TRIM_C);
    box(trim, 3.7, 0.14, 0.22, BX - 4.2, 1.08, front - 0.1, TRIM_C);
    // door (propped open against the wall)
    box(trim, 0.08, 2.3, 1.0, DOOR_X - DOOR_W / 2 - 0.04, 1.15, front - 0.55, 0x5C3A22);
    // foundation
    box(trim, W + 0.3, 0.3, D + 0.3, BX, 0.15, BZ, 0x8A8278);

    // neon sign
    const t = KW.textures.sign('GRUMPY\'S', 'neon', 'Burgers · Cold Beer');
    const sm = new THREE.MeshLambertMaterial({ map: t, emissive: new THREE.Color(0xFF8A5C), emissiveMap: t });
    sm.userData = { dayGlow: 0.2, nightGlow: 1.0 };
    KW.env.emissiveMats.push(sm);
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(9, 2.25), sm);
    sign.position.set(BX, H + 0.7, front - 0.36);
    signs.push(sign);

    B.flush(scene, signs);
  }

  function buildInterior(scene, colliders) {
    const T = KW.textures;
    const front = BZ - D / 2, back = BZ + D / 2;

    // floor & ceiling
    const fl = T.woodFloor();
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(W - 0.4, D - 0.4),
      new THREE.MeshPhongMaterial({ map: fl.map, bumpMap: fl.bumpMap, bumpScale: 0.02, shininess: 30, specular: 0x443322 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(BX, 0.06, BZ);
    floor.material.map.repeat.set(4, 3);
    floor.material.bumpMap.repeat.set(4, 3);
    scene.add(floor);
    const ceil = new THREE.Mesh(new THREE.PlaneGeometry(W - 0.2, D - 0.2),
      new THREE.MeshLambertMaterial({ color: 0x2E2520 }));
    ceil.rotation.x = Math.PI / 2;
    ceil.position.set(BX, H - 0.5, BZ);
    scene.add(ceil);

    const batch = new KW.util.GeoBatch();
    const bx = (w, h, d, x, y, z, c) => batch.box(w, h, d, x, y, z, c);

    // ---- the bar (along the back wall) ----
    const barZ = back - 1.9;
    bx(10, 1.12, 0.7, BX - 1, 0.56, barZ, 0x3A2614);             // counter body
    colliders.push({ minX: BX - 6, maxX: BX + 4, minZ: barZ - 0.45, maxZ: back });
    const topTex = T.barTop();
    const top = new THREE.Mesh(new THREE.PlaneGeometry(10.4, 0.95),
      new THREE.MeshPhongMaterial({ map: topTex.map, shininess: 70, specular: 0x886644 }));
    top.rotation.x = -Math.PI / 2;
    top.position.set(BX - 1, 1.13, barZ);
    scene.add(top);
    bx(10, 0.12, 0.16, BX - 1, 0.16, barZ - 0.42, 0x8A6D3B);     // brass foot rail

    // back bar shelving + bottles
    bx(9.6, 0.08, 0.5, BX - 1, 1.5, back - 0.35, 0x4A3017);
    bx(9.6, 0.08, 0.5, BX - 1, 2.1, back - 0.35, 0x4A3017);
    const r = KW.util.rng(99);
    const bottleCols = [0x3A6E2A, 0x6E3A1A, 0x2A3A6E, 0xC8A23C, 0x842A2A, 0x4A4A4A];
    for (let shelf = 0; shelf < 2; shelf++) {
      for (let i = 0; i < 16; i++) {
        const px = BX - 5.4 + i * 0.58 + r() * 0.12;
        const g = new THREE.CylinderGeometry(0.05, 0.06, 0.32, 6);
        batch.add(g, new THREE.Matrix4().setPosition(px, 1.54 + shelf * 0.6 + 0.16, back - 0.35),
          bottleCols[(i * 5 + shelf) % bottleCols.length]);
      }
    }
    // taps
    for (let i = 0; i < 4; i++) {
      bx(0.06, 0.34, 0.06, BX - 2.4 + i * 0.5, 1.36, barZ - 0.1, 0xC9C4B4);
      bx(0.1, 0.08, 0.1, BX - 2.4 + i * 0.5, 1.56, barZ - 0.1, 0x8A2A22);
    }
    bx(2.4, 0.3, 0.3, BX - 1.65, 1.18, barZ - 0.1, 0x2A2A2E); // tap trough

    // stools
    for (let i = 0; i < 5; i++) {
      const sx = BX - 5 + i * 2;
      const g = new THREE.CylinderGeometry(0.24, 0.24, 0.08, 10);
      batch.add(g, new THREE.Matrix4().setPosition(sx, 0.78, barZ - 1.0), 0x6E2F28);
      const leg = new THREE.CylinderGeometry(0.04, 0.05, 0.76, 8);
      batch.add(leg, new THREE.Matrix4().setPosition(sx, 0.39, barZ - 1.0), 0x222222);
    }

    // communal tables
    KW.props.begin();
    KW.props.picnicTable(BX - 4, BZ - 2.2, 0.04);
    KW.props.picnicTable(BX + 1.5, BZ - 2.0, -0.06);
    colliders.push({ minX: BX - 5.3, maxX: BX - 2.7, minZ: BZ - 3.2, maxZ: BZ - 1.2 });
    colliders.push({ minX: BX + 0.2, maxX: BX + 2.8, minZ: BZ - 3.0, maxZ: BZ - 1.0 });
    KW.props.flush(scene);

    // wall paneling wainscot + memorabilia boards
    bx(W - 0.5, 1.2, 0.08, BX, 0.66, back - WALL / 2 - 0.06, 0x4E3A26);
    for (let i = 0; i < 7; i++) { // license plates / photos
      bx(0.42, 0.22, 0.03, BX - 5.5 + i * 1.4 + r() * 0.5, 2.6 + r() * 0.8, back - WALL / 2 - 0.05,
        [0xC8B43C, 0x8A9AB0, 0xB05C47, 0xD8D2C4][i % 4]);
    }
    const m = new THREE.Mesh(batch.merge(), new THREE.MeshLambertMaterial({ vertexColors: true }));
    m.castShadow = false;
    scene.add(m);

    // TV above the bar, mid-game
    const tv = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 0.95),
      new THREE.MeshBasicMaterial({ map: KW.textures.tvScreen() }));
    tv.position.set(BX + 3.2, 2.9, back - WALL / 2 - 0.12);
    tv.rotation.y = Math.PI;
    // MeshBasic ignores fog/light — reads as a lit screen
    scene.add(tv);
    const tvFrame = new THREE.Mesh(new THREE.BoxGeometry(1.84, 1.08, 0.1),
      new THREE.MeshLambertMaterial({ color: 0x111111 }));
    tvFrame.position.set(BX + 3.2, 2.9, back - WALL / 2 - 0.05);
    scene.add(tvFrame);

    // interior neon
    const nt = KW.textures.sign('GRUMPY\'S', 'neon');
    const nm = new THREE.MeshLambertMaterial({ map: nt, emissive: new THREE.Color(0xFF8A5C), emissiveMap: nt });
    nm.userData = { dayGlow: 0.35, nightGlow: 1.0 };
    KW.env.emissiveMats.push(nm);
    const neon = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 0.8), nm);
    neon.position.set(BX - 1, 3.3, back - WALL / 2 - 0.08);
    neon.rotation.y = Math.PI;
    scene.add(neon);

    // pendant lights — always on; warmer & brighter at night
    for (const px of [BX - 3, BX + 1.5]) {
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 6),
        new THREE.MeshLambertMaterial({ color: 0xFFF2CF, emissive: 0xFFDF9A, emissiveIntensity: 0.8 }));
      bulb.position.set(px, 2.75, BZ - 1);
      scene.add(bulb);
      const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, H - 0.5 - 2.75, 4),
        new THREE.MeshLambertMaterial({ color: 0x191512 }));
      cord.position.set(px, (H - 0.5 + 2.75) / 2, BZ - 1);
      scene.add(cord);
      const light = new THREE.PointLight(0xFFD9A0, 0.55, 11, 1.6);
      light.position.set(px, 2.7, BZ - 1);
      light.userData = { dayI: 0.55, nightI: 0.95 };
      KW.env.pointLights.push(light);
      scene.add(light);
    }
  }

  function buildGrounds(ctx) {
    const scene = ctx.scene;
    const T = KW.textures;
    // Warm Springs Rd extension
    const asph = T.asphalt();
    const road = new THREE.Mesh(new THREE.PlaneGeometry(190, G.STREET_W),
      new THREE.MeshPhongMaterial({ map: asph.map, bumpMap: asph.bumpMap, bumpScale: 0.02, shininess: 8, specular: 0x333333 }));
    road.material.map.repeat.set(30, 2);
    road.material.bumpMap.repeat.set(30, 2);
    road.rotation.x = -Math.PI / 2;
    road.position.set(-228 - 95 + 10, 0.02, ROAD_Z);
    road.receiveShadow = true;
    scene.add(road);

    // gravel lot & beer garden pad
    const gv = T.gravel();
    const lot = new THREE.Mesh(new THREE.PlaneGeometry(50, 34),
      new THREE.MeshPhongMaterial({ map: gv.map, bumpMap: gv.bumpMap, bumpScale: 0.03, shininess: 2 }));
    lot.material.map.repeat.set(10, 7);
    lot.material.bumpMap.repeat.set(10, 7);
    lot.rotation.x = -Math.PI / 2;
    lot.position.set(BX + 4, 0.03, BZ + 2);
    lot.receiveShadow = true;
    scene.add(lot);

    KW.props.begin();
    KW.props.streetSign(-240, ROAD_Z - G.STREET_W / 2 - 1.2, null, 'Warm Springs Rd');
    // beer garden east of the building
    const gx = BX + 13;
    for (const [px, pz, ry] of [[gx - 1.5, BZ - 2, 0.3], [gx + 2.5, BZ - 1, -0.2], [gx + 0.5, BZ + 3, 0.1]]) {
      KW.props.picnicTable(px, pz, ry);
      ctx.colliders.push({ minX: px - 1.3, maxX: px + 1.3, minZ: pz - 1.1, maxZ: pz + 1.1 });
    }
    // string-light posts + festoons
    const postY = 3.2;
    for (const [px, pz] of [[gx - 4, BZ - 4.5], [gx + 5, BZ - 4.5], [gx + 5, BZ + 5.5], [gx - 4, BZ + 5.5]]) {
      KW.props.streetSign(px, pz, null, null); // bare pole
    }
    KW.props.stringLights(gx - 4, postY, BZ - 4.5, gx + 5, postY, BZ - 4.5);
    KW.props.stringLights(gx + 5, postY, BZ - 4.5, gx + 5, postY, BZ + 5.5);
    KW.props.stringLights(gx + 5, postY, BZ + 5.5, gx - 4, postY, BZ + 5.5);
    KW.props.stringLights(gx - 4, postY, BZ + 5.5, gx - 4, postY, BZ - 4.5);
    // a couple of dusty trucks out front
    KW.props.car(BX - 12, ROAD_Z + 11, 0.2, 0x7A3B30, 1);
    KW.props.car(BX + 16, ROAD_Z + 10, -0.15, 0x5A6E76, 0);
    KW.props.flush(ctx.scene);

    // cottonwoods around the lot
    for (const [tx, tz, s] of [[BX - 14, BZ + 6, 1.2], [BX + 24, BZ - 2, 1.4], [BX + 20, BZ + 9, 1.0]]) {
      ctx.trees.push({ x: tx, z: tz, type: 1, s });
    }
  }

  KW.registerDistrict({
    id: 'grumpys',
    name: "Grumpy's — Warm Springs Rd",
    bounds: { minX: -400, maxX: -180, minZ: ROAD_Z - 40, maxZ: ROAD_Z + 60 },
    streets: [],
    avenues: [],

    build(ctx) {
      buildGrounds(ctx);
      buildShell(ctx.scene, ctx.colliders);
      buildInterior(ctx.scene, ctx.colliders);

      ctx.plaques.push({
        x: DOOR_X + 2.5, z: BZ - D / 2 - 2, title: "Grumpy's",
        text: 'No sign out front for years and it never mattered — everyone knows Grumpy\'s. Burgers in plastic baskets, peanut shells underfoot, and the famous schooner: a 32-ounce goblet of cold beer that is basically the town trophy. Carry one to the deck and watch Baldy turn gold.',
      });

      // the bar itself — order a schooner here
      ctx.interactables.push({
        x: BX - 1, z: BZ + D / 2 - 2.6, r: 2.4,
        label: 'Press E to order a schooner',
        action: 'orderSchooner',
      });
    },
  });
})();
