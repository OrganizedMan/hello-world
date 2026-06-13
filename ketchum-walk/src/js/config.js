/**
 * KW — Ketchum Walk global namespace.
 *
 * Expansion packs: a district file calls KW.registerDistrict({...}) with:
 *   id        — unique string
 *   build(ctx)— adds meshes to ctx.scene, colliders to ctx.colliders,
 *               plaques to ctx.plaques, minimap shapes to ctx.map
 * Districts are built once at startup in registration order.
 *
 * Visual-upgrade hooks live in KW.quality (a later sprint can raise these
 * or swap materials without touching district data).
 */
window.KW = {
  districts: [],
  registerDistrict(d) { this.districts.push(d); },

  quality: {
    shadows: true,
    shadowMapSize: 2048,
    pixelRatioCap: 2,
    fogDay: { color: 0xe9c69a, near: 260, far: 2700 },
    fogNight: { color: 0x0a1020, near: 100, far: 1300 },
  },

  // World layout constants (shared by districts so streets line up
  // across future expansion packs). North is -Z, East is +X. Units: meters.
  grid: {
    PITCH: 94,        // street centerline to next street centerline
    STREET_W: 13,     // ordinary street width incl. parking
    MAIN_W: 19,       // Main St (Hwy 75) is wider
    SIDEWALK: 3.2,
  },

  state: {
    night: false,
    mapVisible: true,
  },
};
