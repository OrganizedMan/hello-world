/* Real-world landmark registry for the Google 3D Tiles build.
 *
 * Coordinates are decimal lat/lon (WGS84), accurate to roughly a parcel.
 * If a marker lands a door or two off, nudge it here — with the ?debug=1
 * URL flag the HUD shows your live lat/lon, so you can stand at the real
 * spot in-game and copy the values straight in.
 *
 * The world is laid out in local ENU meters around ORIGIN:
 * +X = east, +Z = south, Y up.
 */
KW.places = (function () {
  const ORIGIN = { lat: 43.68060, lon: -114.36405 }; // Main St & 4th St
  const M_PER_DEG_LAT = 110967;                       // at 43.68° N
  const M_PER_DEG_LON = 80616;

  function toLocal(lat, lon) {
    return {
      x: (lon - ORIGIN.lon) * M_PER_DEG_LON,
      z: -(lat - ORIGIN.lat) * M_PER_DEG_LAT,
    };
  }
  function toGeo(x, z) {
    return {
      lat: ORIGIN.lat - z / M_PER_DEG_LAT,
      lon: ORIGIN.lon + x / M_PER_DEG_LON,
    };
  }

  const LANDMARKS = [
    { lat: 43.68118, lon: -114.36426, title: 'Pioneer Saloon',
      text: 'A Ketchum institution since the 1950s — "the Pio" to locals. Famous for prime rib, an interior packed with mining and hunting relics, and the neon sign that anchors Main Street after dark.' },
    { lat: 43.68035, lon: -114.36390, title: 'Casino Club',
      text: 'Open since 1936 and Ketchum’s oldest bar. The name is no joke — slot machines and card tables ran here back when this was a rowdy sheep and mining town, decades before the ski crowds arrived.' },
    { lat: 43.67878, lon: -114.36531, title: 'Limelight Hotel',
      text: 'A modern mountain lodge at the south gateway of downtown, a short stroll from the River Run lifts. Ski boots in the lounge all winter, bikes against the patio all summer.' },
    { lat: 43.68071, lon: -114.36315, title: 'Ketchum Town Square',
      text: 'The community’s living room at 4th & East Ave — fire pit, summer concerts, art fairs and the farmers’ market. If something is happening in Ketchum, it usually starts here.' },
    { lat: 43.68087, lon: -114.36229, title: 'Atkinsons’ Market — Giacobbi Square',
      text: 'The Atkinson family has fed this valley since 1956. Part grocery, part town crossroads: in a town of a few thousand people, you will run into someone you know in these aisles.' },
    { lat: 43.67918, lon: -114.36558, title: 'Ketchum–Sun Valley Heritage & Ski Museum',
      text: 'Set in Forest Service Park: Union Pacific inventing the destination ski resort in 1936, the world’s first chairlifts, and Ernest Hemingway, who finished "For Whom the Bell Tolls" here and made Ketchum his final home in 1959.' },
    { lat: 43.67815, lon: -114.36620, title: 'Bald Mountain',
      text: 'Look southwest: "Baldy," 9,150 feet, rises straight off the edge of town — 3,400 continuous vertical feet of skiing with no flats. Racers and locals call it one of the best ski hills anywhere.' },
    { lat: 43.68101, lon: -114.36281, title: 'The Elephant’s Perch',
      text: 'The valley’s legendary backcountry shop, named after a granite wall in the Sawtooths. Since the 1970s this is where you come for skis, climbing beta, and an honest answer about tomorrow’s snow.' },
  ];

  // Grumpy's — 860 Warm Springs Rd
  const GRUMPYS = { lat: 43.68530, lon: -114.37404 };

  return { ORIGIN, toLocal, toGeo, LANDMARKS, GRUMPYS };
})();
