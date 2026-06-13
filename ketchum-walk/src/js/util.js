/* Utilities: seeded RNG and geometry merging (keeps draw calls low). */
KW.util = (function () {
  // Mulberry32 — deterministic town layout between runs.
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function pick(r, arr) { return arr[Math.floor(r() * arr.length)]; }

  /**
   * GeoBatch — accumulates transformed, vertex-colored geometry and emits
   * a single merged BufferGeometry. All inputs are converted to
   * non-indexed position/normal/uv/color.
   */
  function GeoBatch() { this.items = []; this.count = 0; }
  GeoBatch.prototype.add = function (geometry, matrix, color, uvScale) {
    let g = geometry.index ? geometry.toNonIndexed() : geometry.clone();
    if (matrix) g.applyMatrix4(matrix);
    if (uvScale && g.attributes.uv) {
      const uv = g.attributes.uv;
      for (let i = 0; i < uv.count; i++) {
        uv.setXY(i, uv.getX(i) * uvScale[0], uv.getY(i) * uvScale[1]);
      }
    }
    const n = g.attributes.position.count;
    const c = new Float32Array(n * 3);
    const col = color instanceof THREE.Color ? color : new THREE.Color(color === undefined ? 0xffffff : color);
    for (let i = 0; i < n; i++) { c[i * 3] = col.r; c[i * 3 + 1] = col.g; c[i * 3 + 2] = col.b; }
    g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    this.items.push(g);
    this.count += n;
    return this;
  };
  GeoBatch.prototype.box = function (w, h, d, x, y, z, color, ry, uvWorldScale) {
    const g = new THREE.BoxGeometry(w, h, d);
    const m = new THREE.Matrix4();
    if (ry) m.makeRotationY(ry);
    m.setPosition(x, y, z);
    // Box UVs are 0..1 per face; scale by face size so texture density is uniform.
    const us = uvWorldScale ? [Math.max(w, d) * uvWorldScale, h * uvWorldScale] : null;
    return this.add(g, m, color, us);
  };
  GeoBatch.prototype.merge = function () {
    if (!this.items.length) return null;
    const total = this.count;
    const pos = new Float32Array(total * 3);
    const nor = new Float32Array(total * 3);
    const uv = new Float32Array(total * 2);
    const col = new Float32Array(total * 3);
    let o = 0;
    for (const g of this.items) {
      const n = g.attributes.position.count;
      pos.set(g.attributes.position.array, o * 3);
      nor.set(g.attributes.normal.array, o * 3);
      if (g.attributes.uv) uv.set(g.attributes.uv.array, o * 2);
      col.set(g.attributes.color.array, o * 3);
      o += n;
      g.dispose();
    }
    const out = new THREE.BufferGeometry();
    out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    out.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
    out.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    out.setAttribute('color', new THREE.BufferAttribute(col, 3));
    this.items = []; this.count = 0;
    return out;
  };

  return { rng, pick, GeoBatch };
})();
