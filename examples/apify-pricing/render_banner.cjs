// Optional raster export; not needed by the offline worksheet or default CI.
// Install @resvg/resvg-js@2.6.2 in an isolated Node environment to regenerate.
const fs = require('node:fs');
const path = require('node:path');
const { Resvg } = require('@resvg/resvg-js');
const root = __dirname;
const svg = fs.readFileSync(path.join(root, 'visuals', 'banner.svg'));
fs.writeFileSync(path.join(root, 'visuals', 'banner.png'), new Resvg(svg, {
  fitTo: { mode: 'width', value: 1200 },
  font: { loadSystemFonts: true, defaultFontFamily: 'Arial' },
}).render().asPng());
console.log('Rendered editorial banner.png (1200 x 630).');
