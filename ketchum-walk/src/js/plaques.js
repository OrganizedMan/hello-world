/* Landmark info plaques: show a panel when the player is near a marker. */
KW.plaques = (function () {
  const Q = {};
  let plaques = [];
  let el, elTitle, elText, current = null;
  const RANGE = 7;

  Q.init = function (list) {
    plaques = list;
    el = document.getElementById('plaque');
    elTitle = el.querySelector('h3');
    elText = el.querySelector('p');
  };

  Q.update = function (pos) {
    let best = null, bestD = RANGE;
    for (const p of plaques) {
      const d = Math.hypot(pos.x - p.x, pos.z - p.z);
      if (d < bestD) { bestD = d; best = p; }
    }
    if (best !== current) {
      current = best;
      if (best) {
        elTitle.textContent = best.title;
        elText.textContent = best.text;
        el.classList.add('visible');
      } else {
        el.classList.remove('visible');
      }
    }
  };

  return Q;
})();
