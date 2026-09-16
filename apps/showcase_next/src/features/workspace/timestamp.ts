export function parseTimestamp(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value > 0 ? (value < 1e11 ? value * 1000 : value) : fallback;
  if (typeof value === 'string' && value.trim()) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) return numeric > 0 ? (numeric < 1e11 ? numeric * 1000 : numeric) : fallback;
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }
  return fallback;
}

export function timestampIso(value: unknown, fallback = 0): string | null {
  const timestamp = parseTimestamp(value, fallback);
  return timestamp > 0 ? new Date(timestamp).toISOString() : null;
}
