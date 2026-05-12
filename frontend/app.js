const API_URL = (window.APP_CONFIG && window.APP_CONFIG.API_URL) || 'http://localhost:8000';
let priceChart = null;
let currentPredictions = [];

function fmt(price) {
  return '₩' + Math.round(price).toLocaleString('ko-KR');
}

function changeClass(val) {
  return val >= 0 ? 'up' : 'down';
}

function changeText(change, pct) {
  const arrow = change >= 0 ? '▲' : '▼';
  const sign = change >= 0 ? '+' : '';
  return `${arrow} ${sign}${Math.round(change).toLocaleString('ko-KR')}원 (${sign}${pct}%)`;
}

function confColor(conf) {
  if (conf >= 85) return '#22c55e';
  if (conf >= 70) return '#f59e0b';
  return '#ef4444';
}

async function loadCurrentPrice() {
  const res = await fetch(`${API_URL}/current-price`);
  const d = await res.json();
  document.getElementById('current-price').textContent = fmt(d.price);
  const chEl = document.getElementById('current-change');
  chEl.textContent = changeText(d.change, d.change_pct);
  chEl.className = 'card-change ' + changeClass(d.change);
  document.getElementById('updated-at').textContent = '마지막 갱신: ' + d.updated_at;
  document.getElementById('update-badge').textContent = '실시간 업데이트';
}

async function loadPredictions() {
  const res = await fetch(`${API_URL}/prediction`);
  const d = await res.json();
  currentPredictions = d.predictions;

  const last = d.predictions[d.predictions.length - 1];
  document.getElementById('predict-price').textContent = fmt(last.price);
  const pchEl = document.getElementById('predict-change');
  pchEl.textContent = changeText(last.change, last.change_pct);
  pchEl.className = 'card-change ' + changeClass(last.change);

  document.getElementById('forecast-rows').innerHTML = d.predictions.map(p => `
    <div class="ft-row">
      <div class="ft-day">${p.day_label}</div>
      <div class="ft-price">${fmt(p.price)}</div>
      <div class="ft-change ${changeClass(p.change)}">${changeText(p.change, p.change_pct)}</div>
      <div class="ft-conf-wrap">
        <div class="ft-bar"><div class="ft-bar-fill" style="width:${p.confidence}%;background:${confColor(p.confidence)};"></div></div>
        <div class="ft-conf-text">${p.confidence}%</div>
      </div>
    </div>
  `).join('');
}

async function loadChart(days = 30) {
  const res = await fetch(`${API_URL}/history?days=${days}`);
  const hist = await res.json();
  const histLen = hist.dates.length;

  const histData = hist.prices.map((p, i) => ({ x: hist.dates[i], y: p }));
  const predConnected = [
    { x: hist.dates[histLen - 1], y: hist.prices[histLen - 1] },
    ...currentPredictions.map(p => ({ x: p.date, y: p.price }))
  ];

  if (priceChart) priceChart.destroy();

  priceChart = new Chart(document.getElementById('price-chart'), {
    type: 'line',
    data: {
      datasets: [
        {
          label: '실제 주가',
          data: histData,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.08)',
          borderWidth: 2,
          pointRadius: 0,
          fill: true,
          tension: 0.3,
        },
        {
          label: 'AI 예측',
          data: predConnected,
          borderColor: '#a78bfa',
          backgroundColor: 'rgba(167,139,250,0.08)',
          borderWidth: 2,
          borderDash: [6, 3],
          pointRadius: 3,
          pointBackgroundColor: '#a78bfa',
          fill: true,
          tension: 0.3,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.parsed.y)}` } }
      },
      scales: {
        x: { type: 'category', ticks: { color: '#475569', maxTicksLimit: 8, font: { size: 10 } }, grid: { color: '#1e293b' } },
        y: { ticks: { color: '#475569', font: { size: 10 }, callback: v => fmt(v) }, grid: { color: '#1e293b' } }
      }
    }
  });
}

async function loadAccuracy() {
  const res = await fetch(`${API_URL}/accuracy`);
  const d = await res.json();
  [['1d', d['1d']], ['3d', d['3d']], ['7d', d['7d']]].forEach(([key, val]) => {
    document.getElementById(`bar-${key}`).style.width = `${val}%`;
    document.getElementById(`val-${key}`).textContent = `${val}%`;
  });
  document.getElementById('acc-1d').textContent = d['1d'] + '%';
}

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    loadChart(parseInt(tab.dataset.days));
  });
});

async function init() {
  await Promise.all([loadCurrentPrice(), loadPredictions(), loadAccuracy()]);
  await loadChart(30);
}

init();
setInterval(init, 30 * 60 * 1000);
