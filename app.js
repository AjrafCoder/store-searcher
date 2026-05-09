'use strict';

const state = {
  deals: [],
  filtered: [],
  sort: { key: 'profit_voucher', dir: 'desc' },
  filters: {
    platforms: new Set(),
    retailers: new Set(),
    minProfit: 1,
    hideSaturated: false,
  },
  meta: {},
};

const fmt = (n) => `£${Number(n).toFixed(2)}`;
const fmtDate = (iso) => {
  try { return new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }); }
  catch { return iso; }
};

async function load() {
  const r = await fetch(`data/deals.json?cb=${Date.now()}`);
  if (!r.ok) throw new Error(`fetch deals.json: ${r.status}`);
  const data = await r.json();
  state.meta = data;
  state.deals = data.deals || [];
  document.getElementById('stat-count').textContent = state.deals.length;
  document.getElementById('stat-profit').textContent = fmt(data.total_potential_profit || 0);
  document.getElementById('stat-min').textContent = fmt(data.min_profit_voucher || 1);
  document.getElementById('stat-updated').textContent = fmtDate(data.generated_at);
  document.getElementById('meta').textContent = `Updated ${fmtDate(data.generated_at)}`;

  if (data.errors && data.errors.length) {
    const box = document.getElementById('errors');
    box.classList.remove('hidden');
    box.textContent = `Scraper warnings: ${data.errors.map(e => e.source).join(', ')}`;
  }

  populateMultiSelect('f-platforms', new Set(state.deals.map(d => d.platform)));
  populateMultiSelect('f-retailers', new Set(state.deals.map(d => d.retailer)));
  bindFilters();
  bindSort();
  apply();
}

function populateMultiSelect(id, values) {
  const sel = document.getElementById(id);
  sel.innerHTML = '';
  [...values].sort().forEach(v => {
    const o = document.createElement('option');
    o.value = v; o.textContent = v; o.selected = true;
    sel.appendChild(o);
  });
}

function bindFilters() {
  document.getElementById('f-platforms').addEventListener('change', apply);
  document.getElementById('f-retailers').addEventListener('change', apply);
  document.getElementById('f-hide-saturated').addEventListener('change', apply);
  const min = document.getElementById('f-min');
  const minLabel = document.getElementById('f-min-label');
  min.addEventListener('input', () => {
    minLabel.textContent = min.value;
    state.filters.minProfit = Number(min.value);
    apply();
  });
}

function bindSort() {
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const k = th.dataset.sort;
      if (state.sort.key === k) state.sort.dir = state.sort.dir === 'asc' ? 'desc' : 'asc';
      else { state.sort.key = k; state.sort.dir = 'desc'; }
      render();
    });
  });
}

function readMulti(id) {
  return new Set([...document.getElementById(id).selectedOptions].map(o => o.value));
}

function apply() {
  state.filters.platforms = readMulti('f-platforms');
  state.filters.retailers = readMulti('f-retailers');
  state.filters.hideSaturated = document.getElementById('f-hide-saturated').checked;
  state.filtered = state.deals.filter(d =>
    state.filters.platforms.has(d.platform) &&
    state.filters.retailers.has(d.retailer) &&
    d.profit_voucher >= state.filters.minProfit &&
    (!state.filters.hideSaturated || d.saturation_risk !== 'high')
  );
  render();
}

function compare(a, b, key, dir) {
  const av = a[key], bv = b[key];
  let cmp;
  if (typeof av === 'number' && typeof bv === 'number') cmp = av - bv;
  else cmp = String(av ?? '').localeCompare(String(bv ?? ''));
  return dir === 'asc' ? cmp : -cmp;
}

function pillClass(level) {
  return `pill pill-${level || 'low'}`;
}

function render() {
  const sorted = [...state.filtered].sort((a, b) => compare(a, b, state.sort.key, state.sort.dir));
  // Desktop table
  const tbody = document.getElementById('rows');
  tbody.innerHTML = sorted.map(d => `
    <tr class="border-t hover:bg-slate-50">
      <td class="px-3 py-2">${escapeHtml(d.title)}</td>
      <td class="px-3 py-2">${escapeHtml(d.platform)}</td>
      <td class="px-3 py-2">${escapeHtml(d.retailer)}</td>
      <td class="px-3 py-2 text-right">${fmt(d.buy_price)}</td>
      <td class="px-3 py-2 text-right">${fmt(d.cex_cash)}</td>
      <td class="px-3 py-2 text-right">${fmt(d.cex_voucher)}</td>
      <td class="px-3 py-2 text-right font-semibold text-emerald-700">${fmt(d.profit_voucher)}</td>
      <td class="px-3 py-2 text-right ${d.profit_cash >= 0 ? 'text-emerald-700' : 'text-slate-400'}">${fmt(d.profit_cash)}</td>
      <td class="px-3 py-2"><span class="${pillClass(d.saturation_risk)}">${d.saturation_risk}</span></td>
      <td class="px-3 py-2 whitespace-nowrap">
        <a class="text-blue-600 hover:underline" target="_blank" rel="noopener" href="${d.buy_url}">Buy</a>
        <span class="text-slate-300 mx-1">·</span>
        <a class="text-blue-600 hover:underline" target="_blank" rel="noopener" href="${d.cex_url}">CeX</a>
      </td>
    </tr>
  `).join('');

  // Mobile cards
  const cards = document.getElementById('cards');
  cards.innerHTML = sorted.map(d => `
    <article class="bg-white rounded-lg shadow-sm p-3">
      <div class="flex items-baseline justify-between gap-2">
        <h3 class="font-semibold text-base">${escapeHtml(d.title)}</h3>
        <span class="${pillClass(d.saturation_risk)}">${d.saturation_risk}</span>
      </div>
      <div class="text-xs text-slate-500 mb-2">${escapeHtml(d.platform)} · ${escapeHtml(d.retailer)}</div>
      <div class="grid grid-cols-3 gap-2 text-sm mb-2">
        <div><div class="text-slate-500 text-xs">Buy</div>${fmt(d.buy_price)}</div>
        <div><div class="text-slate-500 text-xs">Voucher</div>${fmt(d.cex_voucher)}</div>
        <div><div class="text-slate-500 text-xs">Profit</div><span class="font-semibold text-emerald-700">${fmt(d.profit_voucher)}</span></div>
      </div>
      <div class="flex gap-2">
        <a href="${d.buy_url}" target="_blank" rel="noopener" class="flex-1 text-center bg-blue-600 text-white rounded py-1.5 text-sm">Buy</a>
        <a href="${d.cex_url}" target="_blank" rel="noopener" class="flex-1 text-center bg-slate-800 text-white rounded py-1.5 text-sm">CeX</a>
      </div>
    </article>
  `).join('');
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

load().catch(err => {
  document.getElementById('rows').innerHTML =
    `<tr><td class="px-3 py-4 text-red-600" colspan="10">Failed to load: ${escapeHtml(err.message)}</td></tr>`;
});
