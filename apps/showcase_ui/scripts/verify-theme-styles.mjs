import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const tokens = await readFile(resolve(root, 'src/styles/theme-tokens.scss'), 'utf8');
const globalStyles = await readFile(resolve(root, 'src/styles.scss'), 'utf8');
const required = [
  '--theme-bg-page', '--theme-bg-surface', '--theme-bg-surface-raised',
  '--theme-text-primary', '--theme-text-secondary', '--theme-text-muted',
  '--theme-border', '--theme-border-strong', '--theme-accent', '--theme-on-accent',
  '--theme-input-bg', '--theme-input-text', '--theme-input-placeholder',
  '--theme-hover', '--theme-selected', '--theme-focus', '--theme-backdrop',
  '--theme-shadow', '--theme-success', '--theme-warning', '--theme-error', '--theme-info'
];
if (!tokens.includes(":root[data-theme='dark']") || !tokens.includes(":root[data-theme='light']")) {
  throw new Error('Expected explicit light and dark token selectors.');
}
for (const token of required) {
  const count = tokens.split(token + ':').length - 1;
  if (count !== 2) throw new Error(`Token ${token} must be defined once per theme; found ${count}.`);
}
if (!tokens.includes('color-scheme: light') || !tokens.includes('color-scheme: dark')) {
  throw new Error('Both themes must declare color-scheme.');
}
if (!globalStyles.includes("@use './styles/theme-tokens'")) {
  throw new Error('Semantic theme tokens are not loaded globally.');
}
if (globalStyles.toLowerCase().includes('filter: invert(')) {
  throw new Error('Global color inversion would recolor media and canvas content.');
}
console.log(`Verified ${required.length} semantic tokens across Light and Dark themes.`);
