# Ketchum, Idaho — Walking Simulator

A first-person 3D walking simulator of downtown Ketchum, Idaho at summer
golden hour. Runs entirely in a browser from a single HTML file — no
install, no server, no internet connection needed.

## How to play (plug and play)

1. Grab `dist/Ketchum-Walking-Simulator.html`.
2. Double-click it (opens in Safari, Chrome, or any modern browser).
3. Click "Take a walk". That's it.

| Key | Action |
|---|---|
| `W A S D` / arrows | Walk |
| Mouse | Look around |
| `Shift` | Jog |
| `N` | Toggle day / night |
| `M` | Show / hide minimap |
| `Esc` | Release the mouse |

Walk up to the gold marker posts at landmarks (Pioneer Saloon, Casino
Club, Town Square, Atkinsons', the Heritage & Ski Museum, Bald Mountain
viewpoint, …) to read about them. Sound on — wind, songbirds, the Big
Wood River to the west, and crickets after dark are all generated
procedurally.

## What's modeled

The real downtown grid: Main St (Hwy 75) with River St through 6th St /
Sun Valley Rd cross streets, and Spruce, Washington, East, Leadville and
Walnut Avenues. Hand-placed landmarks sit at their approximate real
locations; the remaining lots are filled procedurally (seeded, so the
town is identical every run). Bald Mountain rises to the southwest with
its ski runs visible.

## Developing

```bash
node build.js   # writes dist/Ketchum-Walking-Simulator.html
```

No dependencies. Source is modular under `src/js/`; `build.js` inlines
Three.js (vendored in `vendor/`) and all modules into the single output
file.

### Adding an expansion district (future sessions)

1. Create `src/js/districts/<name>.js` modeled on `downtown.js` —
   it calls `KW.registerDistrict({...})` with its own bounds, streets,
   landmarks and a `build(ctx)` function.
2. Keep using `KW.grid` constants so streets line up across districts
   (e.g. Warm Springs extends west of x = -235, the Sun Valley resort
   sits northeast of z = -610).
3. Add the file to `SCRIPTS` in `build.js` and rebuild.

### Visual-upgrade hooks

`KW.quality` (in `src/js/config.js`) centralizes shadow resolution, fog,
and pixel-ratio caps. A later "visual enhancement" sprint can raise these,
swap `MeshLambertMaterial` for PBR materials, or add post-processing in
`main.js` without touching district data.
