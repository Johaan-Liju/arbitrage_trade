const identity = ['dataset', 'symbol', 'expiry', 'specVersion'];
export function timestamp(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value) || !Number.isFinite(Date.parse(value))) throw new Error('Expected an exact UTC timestamp');
  date(value.slice(0, 10));
  return Date.parse(value);
}
function date(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw new Error('Expected an exact calendar date');
}
export function validatePrice(row, specs) {
  if (!['synthetic', 'real'].includes(row.dataset)) throw new Error('Explicit dataset required');
  for (const key of [...identity, 'currency', 'unit', 'source']) if (typeof row[key] !== 'string' || !row[key].trim()) throw new Error(`Missing ${key}`);
  date(row.tradingDate); date(row.expiry);
  if (row.tradingDate > row.expiry) throw new Error('Trading date exceeds expiry');
  const spec = specs.find(s => identity.every(k => s[k] === row[k]));
  if (!spec || spec.currency !== row.currency || spec.unit !== row.unit) throw new Error('Unknown or incompatible contract specification');
  if (!Number.isFinite(row.price) || row.price <= 0) throw new Error('Price must be positive and finite');
  if (timestamp(row.availableAt) < timestamp(row.observedAt)) throw new Error('Availability precedes observation');
  if (timestamp(spec.availableAt) > timestamp(row.availableAt)) throw new Error('Specification was unavailable');
  return row;
}
export function snapshot(rows, specs, selection, asOf) {
  const cutoff = timestamp(asOf);
  if (identity.some(k => !selection[k])) throw new Error('Complete contract identity required');
  const spec = specs.find(s => identity.every(k => s[k] === selection[k]));
  if (!spec || timestamp(spec.availableAt) > cutoff) throw new Error('Specification unavailable as of requested time');
  const prices = rows.map(r => validatePrice(r, specs)).filter(r => identity.every(k => r[k] === selection[k]) && timestamp(r.observedAt) <= cutoff && timestamp(r.availableAt) <= cutoff && r.tradingDate <= asOf.slice(0, 10)).sort((a,b) => timestamp(a.observedAt) - timestamp(b.observedAt));
  return { dataset: selection.dataset, spec, asOf, prices, indicator: { name: 'As-of sample mean', count: prices.length, value: prices.length ? prices.reduce((sum, r) => sum + r.price, 0) / prices.length : null } };
}
