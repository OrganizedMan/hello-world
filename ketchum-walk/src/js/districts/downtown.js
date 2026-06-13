/* DISTRICT: Downtown Ketchum core.
 * Main St (Hwy 75) runs north-south; cross streets River St through 6th /
 * Sun Valley Rd; avenues Spruce & Washington (west), East, Leadville,
 * Walnut (east). Landmarks are hand-placed; the rest of each block is
 * filled procedurally with seeded randomness so the town is stable
 * between runs.
 *
 * EXPANSION PACKS: copy this file's structure. Keep KW.grid constants so
 * streets line up; e.g. a "Warm Springs" district would extend west of
 * x = -235, a "Sun Valley Resort" district north-east of z = -610.
 */
(function () {
  const G = KW.grid;
  const P = G.PITCH;

  // r: cross streets (z = -r * P), c: avenues (x = c * P)
  const STREETS = [
    { r: 0, name: 'River St' },
    { r: 1, name: '1st St' },
    { r: 2, name: '2nd St' },
    { r: 3, name: '3rd St' },
    { r: 4, name: '4th St' },
    { r: 5, name: 'Sun Valley Rd' },
    { r: 6, name: '6th St' },
  ];
  const AVENUES = [
    { c: -2, name: 'Spruce Ave' },
    { c: -1, name: 'Washington Ave' },
    { c: 0, name: 'Main St' },
    { c: 1, name: 'East Ave' },
    { c: 2, name: 'Leadville Ave' },
    { c: 3, name: 'Walnut Ave' },
  ];
  const X_MIN = -2 * P, X_MAX = 3 * P, Z_MIN = -6 * P, Z_MAX = 0;
  const MAIN_OFF = G.MAIN_W / 2 + G.SIDEWALK;   // building front line off Main
  const ST_OFF = G.STREET_W / 2 + G.SIDEWALK;   // off ordinary streets

  const PALETTE = [0xd9cdb2, 0xc4b49a, 0xb7c0b0, 0x9aa7b4, 0xc9a386, 0xb05c47,
    0x8a6f52, 0xddd6c8, 0xa3b08e, 0x97704f];
  const TRIMS = [0x4a3b2c, 0x2e3a40, 0x5c4a36, 0x303030, 0x6e5136];
  const SHOPS = [
    ['STURTEVANTS', 'Mountain Outfitters'], ['CHAPTER ONE', 'Bookstore'],
    ['THE KNEADERY', 'Breakfast & Lunch'], ['ICONOCLAST BOOKS', null],
    ['SILVER CREEK OUTFITTERS', 'Fly Fishing'], ['MAUDE\'S', 'Coffee & Clothes'],
    ['DESPO\'S', 'Mexican Cafe'], ['RICKSHAW', null], ['ENOTECA', 'Wood-Fired Pizza'],
    ['WARFIELD', 'Distillery & Brewery'], ['SUN VALLEY REALTY', null],
    ['GALENA BENCH GALLERY', null], ['BIGWOOD BREAD', 'Bakery Cafe'],
    ['FORMULA SPORTS', null], ['TRAIL CREEK TRADING CO.', null],
    ['LEFTY\'S', 'Bar & Grill'], ['BOARD BIN', 'Skate & Snow'],
    ['STARBUCKS', 'Coffee'], ['VISIT SUN VALLEY', 'Visitor Center'],
    ['GOLD MINE', 'Thrift Store'], ['THE COVEY', null], ['SEGO', 'Restaurant'],
    ['BACKWOODS MOUNTAIN SPORTS', null], ['JANE\'S ARTIFACTS', 'Art & Paper'],
    ['CORNERSTONE', 'Bar & Grill'], ['PERRY\'S', 'Restaurant'],
    ['SAWTOOTH TITLE', null], ['SILVER QUEEN', 'Saloon'], ['THE OPEN ROOM', 'Gallery'],
    ['KENTWOOD LODGE', null], ['LUCKY DOG', 'Consignment'], ['HEMINGWAY\'S', 'Books & Prints'],
    ['ALPINE PEDALER', 'Bike Shop'], ['HOT WATER INN', null], ['VALLEY PADDLE', null],
    ['WISEGUY PIZZA', null], ['THE GRILL AT KNOB HILL', null], ['SUSHI ON SECOND', null],
  ];

  // ---- Landmarks (hand-placed; reserved rects keep filler away) ----
  const E = Math.PI / 2; // front faces east (+X)
  const W = -Math.PI / 2;
  const LANDMARKS = [
    { x: -(MAIN_OFF + 10), z: -3.45 * P, w: 14, d: 20, ry: E, floors: 1, h: 6.2,
      style: 'falsefront', facade: 'batten_dark', trim: 0xE8E0CC, porch: true,
      sign: { text: 'PIONEER SALOON', style: 'neon', hang: true, y: 4.6 } },
    { x: MAIN_OFF + 9, z: -2.42 * P, w: 11, d: 18, ry: W, floors: 1, h: 5.4,
      style: 'falsefront', facade: 'clap_cream', trim: 0x303030,
      sign: { text: 'CASINO', style: 'neon', y: 4.2 } },
    { x: -(MAIN_OFF + 9), z: -2.38 * P, w: 13, d: 18, ry: E, floors: 2,
      style: 'brick', facade: 'brick_red', trim: 0x3a2a1a,
      sign: { text: 'WHISKEY JACQUES\'', style: 'neon', hang: true } },
    { x: MAIN_OFF + 9, z: -2.62 * P, w: 12, d: 18, ry: W, floors: 2,
      style: 'brick', facade: 'brick_tan', trim: 0x2e2620, awning: 'awning_blue',
      sign: { text: 'THE SAWTOOTH CLUB', style: 'paint' } },
    { x: -(MAIN_OFF + 15), z: -0.5 * P, w: 36, d: 28, ry: E, floors: 3, floorH: 3.5,
      style: 'lodge', facade: 'batten_tan', trim: 0x4f4337, sideWindows: 'right',
      sign: { text: 'LIMELIGHT HOTEL', style: 'paint', y: 9.0 } },
    { x: 2 * P + ST_OFF + 14, z: -3.5 * P, w: 30, d: 26, ry: W, floors: 1, h: 7,
      style: 'retail', facade: 'stucco_cream', trim: 0x5c4a36, awning: 'awning_red',
      sign: { text: 'ATKINSONS\' MARKET', style: 'paint', sub: 'Giacobbi Square', y: 4.4 } },
    { x: -1.55 * P, z: -1.4 * P, w: 16, d: 12, ry: 0, floors: 1, h: 4.2,
      style: 'chalet', facade: 'log', trim: 0xE8E0CC, storefront: false, roofColor: 0x44584a,
      sign: { text: 'KETCHUM-SUN VALLEY MUSEUM', style: 'wood', y: 3.4 } },
    { x: MAIN_OFF + 10, z: -3.42 * P, w: 15, d: 20, ry: W, floors: 2,
      style: 'falsefront', facade: 'clap_brown', trim: 0xF2EAD8, porch: true,
      sign: { text: 'WARFIELD', style: 'paint', sub: 'Distillery & Brewery' } },
    { x: P + ST_OFF + 8, z: -2.55 * P, w: 13, d: 15, ry: W, floors: 1, h: 5.0,
      style: 'falsefront', facade: 'clap_sage', trim: 0x2a2118,
      sign: { text: 'THE ELEPHANT\'S PERCH', style: 'wood', hang: true } },
    { x: P + ST_OFF + 9, z: -4.62 * P, w: 16, d: 14, ry: W, floors: 2,
      style: 'brick', facade: 'brick_paint', trim: 0x3c3328,
      sign: { text: 'KETCHUM CITY HALL', style: 'paint' } },
  ];

  // Open spaces (no filler buildings): town square, museum park, plaza behind Atkinsons'
  const RESERVED = [
    { minX: P + 8, maxX: P + 44, minZ: -3.95 * P, maxZ: -3.55 * P },   // Town Square
    { minX: -1.85 * P, maxX: -1.15 * P, minZ: -1.75 * P, maxZ: -1.1 * P }, // Forest Service Park
    { minX: 2 * P + 30, maxX: 3 * P - 10, minZ: -3.9 * P, maxZ: -3.1 * P }, // Giacobbi parking
  ];

  const PLAQUES = [
    { x: -(MAIN_OFF + 1.5), z: -3.45 * P, title: 'Pioneer Saloon',
      text: 'A Ketchum institution since the 1950s — and "the Pio" to locals. Famous for prime rib, an interior packed with mining and hunting relics, and the neon sign that anchors Main Street after dark.' },
    { x: MAIN_OFF + 1.5, z: -2.42 * P, title: 'Casino Club',
      text: 'Open since 1936 and Ketchum’s oldest bar. The name is no joke — slot machines and card tables ran here back when this was a rowdy sheep and mining town, decades before the ski crowds arrived.' },
    { x: -(MAIN_OFF + 2), z: -0.5 * P, title: 'Limelight Hotel',
      text: 'A modern mountain lodge at the south gateway of downtown, a short stroll from the River Run lifts. Its lounge fills with ski boots in winter and bikes lean against the patio all summer.' },
    { x: P + 10, z: -3.7 * P, title: 'Ketchum Town Square',
      text: 'The community’s living room at 4th & East Ave — fire pit, summer concerts, art fairs and the farmers’ market. If something is happening in Ketchum, it usually starts here.' },
    { x: 2 * P + ST_OFF + 1, z: -3.5 * P, title: 'Atkinsons’ Market — Giacobbi Square',
      text: 'The Atkinson family has fed this valley since 1956. Part grocery, part town crossroads: in a town of a few thousand people, you will run into someone you know in these aisles.' },
    { x: -1.55 * P, z: -1.31 * P, title: 'Ketchum–Sun Valley Heritage & Ski Museum',
      text: 'Set in Forest Service Park, the museum tells the valley’s story: Union Pacific inventing the destination ski resort in 1936, the world’s first chairlifts, and Ernest Hemingway, who finished "For Whom the Bell Tolls" here and made Ketchum his final home in 1959.' },
    { x: -3, z: -2, title: 'Bald Mountain',
      text: 'Look southwest: "Baldy," 9,150 feet, rises straight off the edge of town — 3,400 continuous vertical feet of skiing with no flats, which is why racers and locals call it one of the best ski hills anywhere.' },
    { x: P + ST_OFF + 1, z: -2.55 * P, title: 'The Elephant’s Perch',
      text: 'The valley’s legendary backcountry shop, named after a granite wall in the Sawtooths. Since the 1970s this is where you come for skis, climbing beta, and an honest answer about tomorrow’s snow.' },
  ];

  function fillBlocks(specs, rng) {
    const overlaps = (a, b) => a.minX < b.maxX && a.maxX > b.minX && a.minZ < b.maxZ && a.maxZ > b.minZ;
    const blocked = (fp) => {
      for (const r of RESERVED) if (overlaps(fp, r)) return true;
      for (const l of LANDMARKS) if (overlaps(fp, fpOf(l))) return true;
      for (const s of specs) if (overlaps(fp, fpOf(s))) return true;
      return false;
    };
    const fpOf = (s) => {
      const hw = s.w / 2 + 1.2, hd = s.d / 2 + 1.2;
      const swap = Math.abs(Math.sin(s.ry || 0)) > 0.5;
      const ex = swap ? hd : hw, ez = swap ? hw : hd;
      return { minX: s.x - ex, maxX: s.x + ex, minZ: s.z - ez, maxZ: s.z + ez };
    };

    for (let c = -2; c < 3; c++) {
      for (let r = 0; r < 6; r++) {
        const xW = c * P, xE = (c + 1) * P, zS = -r * P, zN = -(r + 1) * P;
        const onMainW = c === 0, onMainE = c === -1; // block borders Main on its west/east side
        const outer = c <= -2 || c >= 2 || r >= 5;

        // Avenue frontages (buildings face east/west)
        for (const side of ['w', 'e']) {
          const facingMain = (side === 'w' && onMainW) || (side === 'e' && onMainE);
          const off = facingMain ? MAIN_OFF : ST_OFF;
          const fx = side === 'w' ? xW + off : xE - off;
          const ry = side === 'w' ? Math.PI / 2 : -Math.PI / 2;
          const density = facingMain ? 1.0 : (outer ? 0.55 : 0.75);
          let cur = zS - (ST_OFF + 6);
          const end = zN + (ST_OFF + 6);
          while (cur > end + 8) {
            const w = 8 + rng() * 8;
            if (cur - w < end) break;
            if (rng() < density) {
              const d = 10 + rng() * 6;
              const cz = cur - w / 2;
              const cx = side === 'w' ? fx + d / 2 : fx - d / 2;
              const s = makeSpec(cx, cz, w, d, ry, facingMain, outer, rng);
              if (!blocked(fpOf(s))) specs.push(s);
            }
            cur -= w + 1.5 + rng() * 6;
          }
        }
        // Cross-street frontages (face north/south) — sparser
        for (const side of ['s', 'n']) {
          const fz = side === 's' ? zS - ST_OFF : zN + ST_OFF;
          const ry = side === 's' ? 0 : Math.PI;
          let cur = xW + (onMainW ? MAIN_OFF : ST_OFF) + 6;
          const end = xE - (onMainE ? MAIN_OFF : ST_OFF) - 6;
          while (cur < end - 8) {
            const w = 8 + rng() * 8;
            if (cur + w > end) break;
            if (rng() < (outer ? 0.45 : 0.6)) {
              const d = 9 + rng() * 6;
              const cx = cur + w / 2;
              const cz = side === 's' ? fz - d / 2 : fz + d / 2;
              const s = makeSpec(cx, cz, w, d, ry, false, outer, rng);
              if (!blocked(fpOf(s))) specs.push(s);
            }
            cur += w + 2 + rng() * 8;
          }
        }
      }
    }
  }

  let shopIdx = 0;
  function makeSpec(x, z, w, d, ry, onMain, outer, rng) {
    const pick = KW.util.pick;
    let style, floors, sign = null, awning = null, storefront = true;
    if (onMain) {
      style = pick(rng, ['falsefront', 'falsefront', 'brick', 'retail']);
      floors = rng() < 0.45 ? 2 : 1;
      if (shopIdx < SHOPS.length && rng() < 0.8) {
        const sh = SHOPS[shopIdx++];
        sign = { text: sh[0], sub: sh[1] || undefined, style: rng() < 0.3 ? 'wood' : 'paint', hang: rng() < 0.3 };
      }
      if (rng() < 0.5) awning = pick(rng, [0x6e2f28, 0x35424a, 0x3f5238, 0x4a3b2c]);
    } else if (outer) {
      style = rng() < 0.6 ? 'chalet' : 'retail';
      floors = style === 'chalet' && rng() < 0.4 ? 2 : 1;
      storefront = style !== 'chalet';
    } else {
      style = pick(rng, ['retail', 'brick', 'falsefront', 'chalet']);
      floors = rng() < 0.3 ? 2 : 1;
      storefront = style !== 'chalet';
      if (shopIdx < SHOPS.length && rng() < 0.3) {
        const sh = SHOPS[shopIdx++];
        sign = { text: sh[0], sub: sh[1] || undefined, style: pick(rng, ['paint', 'wood']) };
      }
    }
    return {
      x, z, w, d, ry, floors, style, sign, awning, storefront,
      color: pick(rng, PALETTE), trim: pick(rng, TRIMS),
      roofColor: pick(rng, [0x4a423a, 0x5c5650, 0x6e3b30, 0x3c4448]),
    };
  }

  function buildGround(scene) {
    const T = KW.textures;
    const asphalt = new KW.util.GeoBatch();
    const walk = new KW.util.GeoBatch();
    const paint = new KW.util.GeoBatch();
    const flat = (batch, w, d, x, z, y, color, uvs) => {
      const g = new THREE.PlaneGeometry(w, d);
      const m = new THREE.Matrix4().makeRotationX(-Math.PI / 2).setPosition(x, y, z);
      batch.add(g, m, color, uvs || [w / 6, d / 6]);
    };

    const xSpanW = (X_MAX - X_MIN) + 60, xMid = (X_MIN + X_MAX) / 2;
    const zSpanW = (Z_MAX - Z_MIN) + 60, zMid = (Z_MIN + Z_MAX) / 2;
    // cross streets
    for (const st of STREETS) flat(asphalt, xSpanW, G.STREET_W, xMid, -st.r * P, 0.02, 0xffffff);
    // avenues
    for (const av of AVENUES) {
      const wdt = av.c === 0 ? G.MAIN_W : G.STREET_W;
      flat(asphalt, wdt, zSpanW + 400, av.c * P, zMid - 100, 0.025, 0xffffff, [wdt / 6, (zSpanW + 400) / 6]);
    }
    // sidewalk aprons under every block, with raised curbs
    for (let c = -2; c < 3; c++) {
      for (let r = 0; r < 6; r++) {
        const x0 = c * P + (c === 0 ? G.MAIN_W / 2 : G.STREET_W / 2);
        const x1 = (c + 1) * P - (c === -1 ? G.MAIN_W / 2 : G.STREET_W / 2);
        const z1 = -r * P - G.STREET_W / 2, z0 = -(r + 1) * P + G.STREET_W / 2;
        flat(walk, x1 - x0, z1 - z0, (x0 + x1) / 2, (z0 + z1) / 2, 0.12, 0xffffff, [(x1 - x0) / 2.4, (z1 - z0) / 2.4]);
        // curb faces
        walk.box(x1 - x0, 0.13, 0.18, (x0 + x1) / 2, 0.065, z1 + 0.02, 0xb8b2a4);
        walk.box(x1 - x0, 0.13, 0.18, (x0 + x1) / 2, 0.065, z0 - 0.02, 0xb8b2a4);
        walk.box(0.18, 0.13, z1 - z0, x0 + 0.02, 0.065, (z0 + z1) / 2, 0xb8b2a4);
        walk.box(0.18, 0.13, z1 - z0, x1 - 0.02, 0.065, (z0 + z1) / 2, 0xb8b2a4);
      }
    }
    // lane dashes on Main + crosswalks + parking stripes
    for (let z = 20; z > Z_MIN - 30; z -= 6) paint.box(0.25, 0.02, 3, 0, 0.06, z, 0xd6b53c);
    for (const st of STREETS) {
      for (const dz of [-1, 1]) {
        for (let i = -3; i <= 3; i++) {
          paint.box(0.7, 0.02, 2.6, i * 1.6, 0.065, -st.r * P + dz * (G.STREET_W / 2 - 1.6), 0xd8d8d2);
        }
      }
    }
    for (let r = 0; r < 6; r++) { // angled-parking ticks along Main
      for (let i = 0; i < 9; i++) {
        const z = -r * P - 14 - i * 7.4;
        for (const sx of [-1, 1]) {
          paint.box(0.14, 0.02, 5.0, sx * (G.MAIN_W / 2 - 2.6), 0.06, z, 0xc8c8c0);
        }
      }
    }

    const asphTex = T.asphalt(), concTex = T.concrete();
    const mA = new THREE.Mesh(asphalt.merge(), new THREE.MeshPhongMaterial({
      map: asphTex.map, bumpMap: asphTex.bumpMap, bumpScale: 0.02,
      shininess: 8, specular: 0x333333, vertexColors: true,
    }));
    const mW = new THREE.Mesh(walk.merge(), new THREE.MeshPhongMaterial({
      map: concTex.map, bumpMap: concTex.bumpMap, bumpScale: 0.015,
      shininess: 3, specular: 0x222222, vertexColors: true,
    }));
    const mP = new THREE.Mesh(paint.merge(), new THREE.MeshLambertMaterial({ vertexColors: true }));
    mA.receiveShadow = mW.receiveShadow = true;
    scene.add(mA, mW, mP);

    // park grass
    const grassT = T.grass().map;
    for (const g of [
      { x: P + 26, z: -3.75 * P, w: 34, d: 34 },        // Town Square green
      { x: -1.5 * P, z: -1.42 * P, w: 60, d: 56 },      // Forest Service Park
    ]) {
      const gm = new THREE.Mesh(new THREE.PlaneGeometry(g.w, g.d),
        new THREE.MeshLambertMaterial({ map: grassT }));
      gm.material.map.repeat.set(g.w / 7, g.d / 7);
      gm.rotation.x = -Math.PI / 2;
      gm.position.set(g.x, 0.14, g.z);
      gm.receiveShadow = true;
      scene.add(gm);
    }
  }

  function placeProps(ctx, rng) {
    const Pr = KW.props;
    // lamps + trees along Main
    for (let r = 0; r < 6; r++) {
      for (const t of [0.25, 0.5, 0.75]) {
        const z = -(r + t) * P;
        for (const sx of [-1, 1]) {
          if (t === 0.5) { Pr.lamp(sx * (G.MAIN_W / 2 + 1.2), z); }
          else ctx.trees.push({ x: sx * (G.MAIN_W / 2 + 1.6), z, type: 0, s: 0.85 + rng() * 0.4 });
        }
      }
    }
    // lamps at every intersection + street signs (stop signs face cross-street traffic at Main)
    for (const st of STREETS) {
      for (const av of AVENUES) {
        const ix = av.c * P, iz = -st.r * P;
        const ow = (av.c === 0 ? G.MAIN_W : G.STREET_W) / 2 + 1.4;
        const oh = G.STREET_W / 2 + 1.4;
        Pr.streetSign(ix + ow, iz + oh, av.name, st.name, av.c === 0 ? Math.PI / 2 : false);
        if (av.c !== 0) Pr.lamp(ix - ow, iz - oh);
        if ((st.r + av.c) % 2 === 0 && av.c !== 0) Pr.hydrant(ix - ow - 0.8, iz + oh + 0.8);
      }
    }
    // alley power lines flanking Main, and along 2nd St
    Pr.powerRun(-47, 10, -47, Z_MIN - 10);
    Pr.powerRun(47, 10, 47, Z_MIN - 10);
    Pr.powerRun(X_MIN - 10, -2 * P - 47, X_MAX + 10, -2 * P - 47);
    // parked vehicles along Main (trucks, SUVs, sedans)
    const carCols = [0x5a6e76, 0x8a8d90, 0x3c4a3a, 0x7a3b30, 0x2c3440, 0xb8b6ae, 0x4f5d73, 0x6e5136];
    for (let i = 0; i < 30; i++) {
      const z = -16 - rng() * (5.6 * P);
      const sx = rng() < 0.5 ? -1 : 1;
      if (Math.abs((z % P + P) % P) < 12) continue; // keep intersections clear
      Pr.car(sx * (G.MAIN_W / 2 - 2.0), z, sx > 0 ? 0 : Math.PI, carCols[i % carCols.length], (i * 7) % 3);
    }
    for (let i = 0; i < 10; i++) {
      const x = 30 + rng() * 120;
      Pr.car(x, -2 * P + (rng() < 0.5 ? -4.6 : 4.6), Math.PI / 2, carCols[(i + 3) % carCols.length], i % 3);
    }

    // Town Square furniture
    const tsx = P + 26, tsz = -3.75 * P;
    Pr.flagpole(tsx, tsz);
    for (let i = 0; i < 4; i++) {
      Pr.bench(tsx - 12 + i * 8, tsz + 12, Math.PI);
      Pr.planter(tsx - 12 + i * 8, tsz - 12);
      ctx.trees.push({ x: tsx - 13 + i * 8.6, z: tsz + (i % 2 ? -16 : 16), type: 0, s: 1.1 });
    }
    // Forest Service Park evergreens
    for (let i = 0; i < 14; i++) {
      ctx.trees.push({
        x: -1.5 * P + (rng() - 0.5) * 52, z: -1.42 * P + (rng() - 0.5) * 48,
        type: 2, s: 1 + rng() * 1.4,
      });
    }
    Pr.bench(-1.5 * P, -1.2 * P, Math.PI);
    // benches + planters down Main
    for (let r = 0; r < 5; r++) {
      Pr.bench(-(G.MAIN_W / 2 + 2.2), -(r + 0.62) * P, Math.PI / 2);
      Pr.planter(G.MAIN_W / 2 + 2.0, -(r + 0.38) * P);
    }
    // cottonwoods along the river + scattered evergreens on the outskirts
    for (let i = 0; i < 34; i++) {
      ctx.trees.push({ x: -305 - rng() * 40, z: 30 - i * 19 - rng() * 8, type: 1, s: 1 + rng() * 0.8 });
    }
    for (let i = 0; i < 40; i++) {
      const ang = rng() * Math.PI * 2, rad = 360 + rng() * 320;
      ctx.trees.push({ x: 50 + Math.cos(ang) * rad, z: -280 + Math.sin(ang) * rad, type: 2, s: 1.2 + rng() * 1.6 });
    }
  }

  KW.registerDistrict({
    id: 'downtown',
    name: 'Downtown Ketchum',
    bounds: { minX: X_MIN - 24, maxX: X_MAX + 24, minZ: Z_MIN - 24, maxZ: Z_MAX + 30 },
    spawn: { x: 3.5, z: -30, yaw: 0 },  // south Main, looking north into town
    streets: STREETS.map((s) => ({ z: -s.r * P, name: s.name })),
    avenues: AVENUES.map((a) => ({ x: a.c * P, name: a.name })),

    build(ctx) {
      const rng = KW.util.rng(20260612);
      buildGround(ctx.scene);

      const specs = LANDMARKS.slice();
      fillBlocks(specs, rng);
      KW.buildings.generate(specs, ctx.scene, ctx.colliders);

      KW.props.begin();
      placeProps(ctx, rng);
      for (const pl of PLAQUES) {
        KW.props.plaqueMarker(pl.x, pl.z);
        ctx.plaques.push(pl);
      }
      KW.props.flush(ctx.scene);
    },
  });
})();
