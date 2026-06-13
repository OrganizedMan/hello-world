#!/usr/bin/env node
/* Builds the real-world (Google Photorealistic 3D Tiles) version into a
 * single HTML file: dist/Ketchum-RealWorld.html
 * Usage: node realworld/build-real.js   (run `npm install` in realworld/ first) */
const fs = require('fs');
const path = require('path');
const esbuild = require('esbuild');

const ROOT = path.join(__dirname, '..');

async function main() {
  const stamp = 'build ' + new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
  const result = await esbuild.build({
    entryPoints: [path.join(__dirname, 'src/entry-real.js')],
    bundle: true,
    minify: true,
    format: 'iife',
    write: false,
    target: 'es2020',
    logLevel: 'warning',
  });
  const js = result.outputFiles[0].text;

  let css = fs.readFileSync(path.join(ROOT, 'src/style.css'), 'utf8');
  css += `
#apikey {
  display: block; width: 100%; box-sizing: border-box; margin: 0 0 14px;
  background: rgba(0,0,0,0.4); border: 1px solid #8a6d3b; border-radius: 8px;
  color: #f3e9d8; font-size: 14px; padding: 10px 14px; outline: none;
}
#apikey:focus { border-color: #d68a2e; }
.keylabel { font-size: 12px; color: #c9b89a; display: block; text-align: left; margin-bottom: 6px; }
.keylabel a { color: #ffd9a0; }
#loading, #tileerror {
  position: fixed; top: 64px; left: 50%; transform: translateX(-50%);
  background: rgba(24,17,10,0.88); border: 1px solid rgba(214,170,100,0.6);
  border-radius: 10px; padding: 12px 22px; color: #f1e7d4; font-size: 14px;
  display: none; z-index: 20; max-width: 520px; text-align: center; line-height: 1.5;
}
#tileerror { border-color: #c0533c; }
`;

  let ui = fs.readFileSync(path.join(ROOT, 'src/ui.html'), 'utf8');
  ui = ui.replace('<div class="start">Click to take a walk</div>',
    `<span class="keylabel">Google Maps Platform API key (Map Tiles API) — stored only in your browser ·
       <a href="https://developers.google.com/maps/documentation/tile/get-api-key" target="_blank">how to get one</a></span>
     <input id="apikey" type="text" placeholder="AIza..." spellcheck="false" autocomplete="off">
     <div class="start" id="startbtn">Walk the real Ketchum</div>`);
  ui = ui.replace('<h2>Idaho &middot; Elev. 5,853 ft</h2>',
    `<h2>Idaho &middot; Elev. 5,853 ft &middot; Real-World Edition<br><span style="font-size:10px;letter-spacing:1px;opacity:0.6">${stamp}</span></h2>`);
  ui += '\n<div id="loading">Streaming Ketchum from Google&hellip; first load takes a moment</div>\n<div id="tileerror"></div>';

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ketchum, Idaho — Real-World Walking Simulator</title>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<style>
${css}
</style>
</head>
<body>
${ui}
<script>
window.KW_BUILD = '${stamp}';
window.addEventListener('error', function (e) {
  var d = document.getElementById('tileerror');
  if (d && d.style.display !== 'block') {
    d.style.display = 'block';
    d.innerHTML = '<b>Startup error.</b><br><small>' + (e.message || 'unknown') + '</small>';
  }
});
</script>
<script>
${js}
</script>
</body>
</html>
`;
  const outDir = path.join(ROOT, 'dist');
  fs.mkdirSync(outDir, { recursive: true });
  const out = path.join(outDir, 'Ketchum-RealWorld.html');
  fs.writeFileSync(out, html);
  console.log(`Built ${out} (${(html.length / 1024 / 1024).toFixed(2)} MB)`);
}
main().catch((e) => { console.error(e); process.exit(1); });
