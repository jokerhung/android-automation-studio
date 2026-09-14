import fs from 'node:fs';
const read = (name) => fs.readFileSync(new URL('../src/app/core/i18n/' + name, import.meta.url), 'utf8');
const entries = (source) => new Map([...source.matchAll(/'([^']+)'\s*:\s*'((?:\\'|[^'])*)'/g)].map((match) => [match[1], match[2]]));
const placeholders = (message) => [...message.matchAll(/{{\s*([^{}\s]+)\s*}}/g)].map((match) => match[1]).sort().join(',');
const en = entries(read('en.ts'));
const vi = entries(read('vi.ts'));
const missing = [...en.keys()].filter((key) => !vi.has(key));
const extra = [...vi.keys()].filter((key) => !en.has(key));
const bad = [...en.keys()].filter((key) => vi.has(key) && placeholders(en.get(key)) !== placeholders(vi.get(key)));
if (missing.length || extra.length || bad.length) { console.error({ missing, extra, placeholderMismatch: bad }); process.exit(1); }
console.log('Catalog parity OK:', en.size, 'keys');
