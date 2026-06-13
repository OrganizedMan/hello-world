# Ketchum, Idaho — Walking Simulator

A first-person walking simulator of Ketchum, Idaho. Two editions, both
single HTML files that open directly in Safari or Chrome:

| File | What it is | Needs |
|---|---|---|
| `dist/Ketchum-RealWorld.html` | **Photoreal.** Streams Google's Photorealistic 3D Tiles — the actual photogrammetry of Ketchum from Google Earth — and runs the walking sim on top. | Internet + a free Google Maps API key |
| `dist/Ketchum-Walking-Simulator.html` | **Offline/stylized.** Fully self-contained procedural recreation of downtown. Works with zero network, zero setup. | Nothing |

## Real-World Edition setup (one time)

1. Get a Google Maps Platform API key and enable the **Map Tiles API**:
   <https://developers.google.com/maps/documentation/tile/get-api-key>
   (Google's free monthly credit comfortably covers personal walking around.)
2. Open `Ketchum-RealWorld.html`, paste the key on the title screen, and
   click **Walk the real Ketchum**. The key is stored only in your
   browser's localStorage. You can also pass it as `?key=AIza...`.

If the key is rejected or tiles fail to load, an on-screen panel explains
what went wrong. Note: photogrammetry detail depends on Google's coverage
of Ketchum; everywhere on Earth at least gets true terrain + aerial
imagery.

## Controls (both editions)

| Key | Action |
|---|---|
| `W A S D` / arrows | Walk |
| Mouse | Look · `Shift` jog |
| `E` | Order a schooner / pick up / enter & leave Grumpy's |
| `F` | Take a drink |
| `G` | Set the schooner down |
| `N` | Day / night |
| `M` | Minimap on/off |
| `Esc` | Release mouse |

## Grumpy's and the schooner

Walk northwest to Grumpy's on Warm Springs Rd (follow the gold beacon),
press `E` at the door to step inside the hand-built bar, and order a
**schooner** — the giant 32 oz goblet of beer that is Grumpy's calling
card. You can carry it anywhere in town, drink it down sip by sip, set it
on the sidewalk, and come back for it later.

In the Real-World Edition, landmark plaques (Pioneer Saloon, Casino Club,
Town Square, Atkinsons', Limelight, the Heritage & Ski Museum…) sit at
their true coordinates under tall gold beacons.

## Developing

```bash
node build.js                      # offline edition → dist/Ketchum-Walking-Simulator.html
cd realworld && npm install && cd ..
node realworld/build-real.js       # real-world edition → dist/Ketchum-RealWorld.html
```

Layout:
- `src/js/` — shared game modules (player, interact/schooner, audio,
  plaques, minimap, textures, props) used by both editions
- `src/js/districts/` — offline edition world data (expansion packs:
  add a file, register it, add to `build.js`)
- `realworld/src/` — tile streaming, real-coordinate places, Grumpy's
  interior pocket, real-world bootstrap

### Calibrating real-world landmark positions

Coordinates live in `realworld/src/places.js`. Open the game with
`?debug=1` to see your live lat/lon in the HUD, stand where a marker
*should* be, and copy the values in. The world is local ENU meters around
Main & 4th: +X east, +Z south, Y up.
