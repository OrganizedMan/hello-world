#!/usr/bin/env node
/**
 * Builds the Ketchum Walking Simulator into a single self-contained HTML file.
 * No dependencies — just `node build.js`. Output: dist/Ketchum-Walking-Simulator.html
 *
 * To add an expansion district in a future session: create
 * src/js/districts/<name>.js (see downtown.js for the registration API)
 * and add it to SCRIPTS below, after downtown.js.
 */
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;

const SCRIPTS = [
  'vendor/three.min.js',
  'src/js/config.js',
  'src/js/util.js',
  'src/js/textures.js',
  'src/js/environment.js',
  'src/js/buildings.js',
  'src/js/props.js',
  'src/js/districts/downtown.js',
  'src/js/districts/grumpys.js',
  'src/js/player.js',
  'src/js/interact.js',
  'src/js/audio.js',
  'src/js/plaques.js',
  'src/js/minimap.js',
  'src/js/main.js',
];

const css = fs.readFileSync(path.join(ROOT, 'src/style.css'), 'utf8');
const ui = fs.readFileSync(path.join(ROOT, 'src/ui.html'), 'utf8');
const js = SCRIPTS.map((f) => {
  const code = fs.readFileSync(path.join(ROOT, f), 'utf8');
  return `/* ==== ${f} ==== */\n${code}`;
}).join('\n');

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ketchum, Idaho — Walking Simulator</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
${css}
</style>
</head>
<body>
${ui}
<script>
${js}
</script>
</body>
</html>
`;

const outDir = path.join(ROOT, 'dist');
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'Ketchum-Walking-Simulator.html');
fs.writeFileSync(outFile, html);
console.log(`Built ${outFile} (${(html.length / 1024 / 1024).toFixed(2)} MB)`);
