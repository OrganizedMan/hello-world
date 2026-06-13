// Bundle entry for the real-world (Google Photorealistic 3D Tiles) build.
// Order matters: globals first (exposes THREE), then the shared game
// modules (classic scripts), then real-world specific modules.
import './globals.js';
import '../../src/js/config.js';
import '../../src/js/util.js';
import '../../src/js/textures.js';
import './env-lite.js';
import '../../src/js/props.js';
import './places.js';
import './grumpys-interior.js';
import '../../src/js/player.js';
import '../../src/js/interact.js';
import '../../src/js/audio.js';
import '../../src/js/plaques.js';
import '../../src/js/minimap.js';
import './main-real.js';
