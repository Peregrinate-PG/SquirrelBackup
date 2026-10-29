// Optional document build dependency: sharp. Does not affect the app build.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
const docs = path.resolve(__dirname, '../docs');
(async () => {
  for (const name of fs.readdirSync(path.join(docs, 'uml/svg'))) {
    if (!name.endsWith('.svg')) continue;
    await sharp(path.join(docs, 'uml/svg', name), { density: 144 })
      .flatten({ background: 'white' }).png()
      .toFile(path.join(docs, 'uml/png', name.replace('.svg', '.png')));
  }
  await sharp(path.join(docs, 'planning/gantt.svg'), { density: 144 })
    .png().toFile(path.join(docs, 'planning/gantt.png'));
})().catch(error => { console.error(error); process.exitCode = 1; });
