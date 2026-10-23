const el = id => document.getElementById(id);
async function refresh(event) {
  event?.preventDefault();
  try {
    const asOf = el('asof').value;
    const response = await fetch(`/api/snapshot?dataset=synthetic&asOf=${encodeURIComponent(asOf.length === 16 ? `${asOf}:00Z` : `${asOf}Z`)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    el('contract').textContent = `${data.spec.symbol} · expires ${data.spec.expiry} · ${data.spec.specVersion}`;
    el('mean').textContent = data.indicator.value === null ? 'No data' : data.indicator.value.toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
    el('count').textContent = data.indicator.count;
    el('prices').replaceChildren(...data.prices.map(row => {
      const tr = document.createElement('tr');
      for (const value of [row.tradingDate, row.symbol, row.expiry, row.specVersion, row.price.toFixed(2), row.availableAt]) { const td = document.createElement('td'); td.textContent = value; tr.append(td); }
      return tr;
    }));
    el('status').textContent = `Synthetic snapshot · cutoff ${data.asOf}`;
  } catch (error) {
    el('prices').replaceChildren(); el('mean').textContent = '—'; el('count').textContent = '—';
    el('status').textContent = `Unable to load snapshot: ${error.message}`;
  }
}
el('query').addEventListener('submit', refresh);
refresh();
