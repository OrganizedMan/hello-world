/* Hideable minimap with street labels, building footprints, plaque dots,
 * and the player arrow. North is up. */
KW.minimap = (function () {
  const M = {};
  let cv, cx, district, colliders, plaques;
  let scale, ox, oz;

  M.init = function (d, cols, pls) {
    district = d; colliders = cols; plaques = pls;
    cv = document.getElementById('minimap');
    cx = cv.getContext('2d');
    const b = d.bounds;
    const pad = 14;
    scale = Math.min((cv.width - pad * 2) / (b.maxX - b.minX), (cv.height - pad * 2) / (b.maxZ - b.minZ));
    ox = pad - b.minX * scale;
    oz = pad - b.minZ * scale;
    if (!KW.state.mapVisible) cv.classList.add('hidden');
  };

  M.toggle = function () {
    KW.state.mapVisible = !KW.state.mapVisible;
    cv.classList.toggle('hidden', !KW.state.mapVisible);
  };

  const px = (x) => x * scale + ox;
  const pz = (z) => z * scale + oz;

  M.draw = function (pos, yaw) {
    if (!KW.state.mapVisible) return;
    const b = district.bounds;
    cx.clearRect(0, 0, cv.width, cv.height);

    // streets
    cx.strokeStyle = 'rgba(220,205,170,0.55)';
    for (const st of district.streets) {
      cx.lineWidth = 3;
      cx.beginPath(); cx.moveTo(px(b.minX), pz(st.z)); cx.lineTo(px(b.maxX), pz(st.z)); cx.stroke();
    }
    for (const av of district.avenues) {
      cx.lineWidth = av.name === 'Main St' ? 5 : 3;
      cx.strokeStyle = av.name === 'Main St' ? 'rgba(240,220,170,0.8)' : 'rgba(220,205,170,0.55)';
      cx.beginPath(); cx.moveTo(px(av.x), pz(b.minZ)); cx.lineTo(px(av.x), pz(b.maxZ)); cx.stroke();
    }

    // buildings
    cx.fillStyle = 'rgba(170,150,120,0.45)';
    for (const c of colliders) {
      cx.fillRect(px(c.minX), pz(c.minZ), (c.maxX - c.minX) * scale, (c.maxZ - c.minZ) * scale);
    }

    // plaques
    cx.fillStyle = '#ffd070';
    for (const p of plaques) {
      cx.beginPath(); cx.arc(px(p.x), pz(p.z), 2.6, 0, 7); cx.fill();
    }

    // labels
    cx.fillStyle = 'rgba(245,235,210,0.9)';
    cx.font = '8px Helvetica, Arial, sans-serif';
    cx.textAlign = 'left';
    for (const st of district.streets) cx.fillText(st.name, 4, pz(st.z) - 2);
    cx.save();
    for (const av of district.avenues) {
      cx.translate(px(av.x) + (av.name === 'Main St' ? -7 : 3), cv.height - 6);
      cx.rotate(-Math.PI / 2);
      cx.fillText(av.name, 0, 6);
      cx.setTransform(1, 0, 0, 1, 0, 0);
    }
    cx.restore();

    // player arrow — yaw 0 faces north (-Z), which is screen-up
    cx.save();
    cx.translate(px(pos.x), pz(pos.z));
    cx.rotate(-yaw);
    cx.fillStyle = '#ff8c4a';
    cx.beginPath();
    cx.moveTo(0, -6); cx.lineTo(4, 5); cx.lineTo(0, 2.5); cx.lineTo(-4, 5);
    cx.closePath(); cx.fill();
    cx.restore();

    // compass N
    cx.fillStyle = 'rgba(245,235,210,0.8)';
    cx.font = 'bold 10px Helvetica';
    cx.fillText('N', cv.width - 14, 12);
  };

  return M;
})();
