// Must be the first import: exposes three.js as the global `THREE` so the
// shared game modules (written as classic scripts) work inside the bundle.
import * as THREE from 'three';
window.THREE = THREE;
