import { readdir, stat } from 'node:fs/promises';
import { extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../out/', import.meta.url));
const limits = {
  totalInitialBytes: 4 * 1024 * 1024,
  totalInitialWarningBytes: 2 * 1024 * 1024,
  singleStyleBytes: 400 * 1024,
  singleStyleWarningBytes: 200 * 1024,
};

async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(entry => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? files(path) : [path];
  }));
  return nested.flat();
}

let all;
try {
  all = await files(root);
} catch (error) {
  console.error('Next export is missing. Run npm run build first.', error);
  process.exit(1);
}

const assets = all.filter(path => ['.js', '.css'].includes(extname(path)));
const measured = await Promise.all(assets.map(async path => ({ path, bytes: (await stat(path)).size })));
const total = measured.reduce((sum, item) => sum + item.bytes, 0);
const oversizedStyles = measured.filter(item => extname(item.path) === '.css' && item.bytes > limits.singleStyleBytes);
const warningStyles = measured.filter(item => extname(item.path) === '.css' && item.bytes > limits.singleStyleWarningBytes);

if (total > limits.totalInitialWarningBytes) console.warn(`Warning: exported JS/CSS is ${total} bytes (Angular baseline warning: 2 MiB).`);
for (const item of warningStyles) console.warn(`Warning: stylesheet ${relative(root, item.path)} is ${item.bytes} bytes (baseline warning: 200 KiB).`);
if (total > limits.totalInitialBytes || oversizedStyles.length) {
  console.error({ totalBytes: total, oversizedStyles: oversizedStyles.map(item => ({ file: relative(root, item.path), bytes: item.bytes })) });
  process.exit(1);
}
console.log(`Next export budget OK: ${measured.length} JS/CSS files, ${total} bytes.`);
