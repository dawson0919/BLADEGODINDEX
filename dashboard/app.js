/* ===========================
   BLADE GOD INDEX — APP.JS
   Real data from /api/blade-index & /api/blade-history
   =========================== */

'use strict';

// ── COLOUR & LABEL HELPERS ─────────────────────────────────────────────────

function scoreColor(s) {
  if (s <= 20) return '#ef4444';
  if (s <= 40) return '#f97316';
  if (s <= 60) return '#eab308';
  if (s <= 80) return '#22c55e';
  return '#3b82f6';
}

function scoreLabel(s) {
  if (s <= 20) return { zh: '極度恐慌', en: 'Extreme Fear' };
  if (s <= 40) return { zh: '恐懼',     en: 'Fear' };
  if (s <= 60) return { zh: '中性觀望', en: 'Neutral' };
  if (s <= 80) return { zh: '市場貪婪', en: 'Greed' };
  return             { zh: '極度貪婪', en: 'Extreme Greed' };
}

function statusBadge(s) {
  if (s <= 20) return { text: '恐慌 Fear',   bg: 'rgba(239,68,68,0.18)',   color: '#ef4444' };
  if (s <= 40) return { text: '恐懼 Fear',   bg: 'rgba(249,115,22,0.18)',  color: '#f97316' };
  if (s <= 60) return { text: '中性 Neutral', bg: 'rgba(234,179,8,0.18)',   color: '#eab308' };
  if (s <= 80) return { text: '貪婪 Greed',   bg: 'rgba(34,197,94,0.18)',   color: '#22c55e' };
  return               { text: '狂熱 Mania',  bg: 'rgba(59,130,246,0.18)', color: '#3b82f6' };
}

// ── MARKET COMMENTARY GENERATOR ────────────────────────────────────────────

function generateCommentary(score, indicators) {
  const lbl = scoreLabel(score);
  const ind  = {};
  (indicators || []).forEach(i => ind[i.id] = i.score);

  let lines = [];

  // Headline
  if (score <= 20) {
    lines.push(`整體刀神指標處於 <strong>極度恐慌</strong> 區間（${score} 分），市場情緒已跌至歷史低位，逢低布局機會浮現，但需留意系統性風險尚未解除。<br/><span class="tip-en">Blade God Index is in <strong>Extreme Fear</strong> territory (${score}). Sentiment at historic lows — potential buy-the-dip opportunity, but systemic risk remains.</span>`);
  } else if (score <= 40) {
    lines.push(`整體刀神指標顯示市場 <strong>恐懼</strong> 情緒（${score} 分），資金持續流向防禦資產，建議謹慎觀望並等待趨勢企穩訊號後再積極入場。<br/><span class="tip-en">Blade God Index signals <strong>Fear</strong> (${score}). Capital flowing to safe havens — stay defensive until trend stabilizes.</span>`);
  } else if (score <= 60) {
    lines.push(`整體刀神指標落在 <strong>刀鋒區域</strong>（${score} 分），多空力量拉鋸，市場方向尚未明確，建議搭配技術面與基本面訊號再決策。<br/><span class="tip-en">Blade God Index in <strong>Blade Zone</strong> (${score}). Bulls and bears deadlocked — confirm direction with technicals & fundamentals.</span>`);
  } else if (score <= 80) {
    lines.push(`整體刀神指標顯示市場 <strong>貪婪</strong> 情緒升溫（${score} 分），多頭動能仍在，但宜逢高適度減碼，警覺短期回調風險。<br/><span class="tip-en">Blade God Index shows rising <strong>Greed</strong> (${score}). Bullish momentum intact, but consider trimming on rallies.</span>`);
  } else {
    lines.push(`整體刀神指標已進入 <strong>極度貪婪</strong> 區間（${score} 分），市場估值普遍偏高、槓桿上升，黑天鵝風險不容忽視，建議大幅降低持倉暴露。<br/><span class="tip-en">Blade God Index in <strong>Extreme Greed</strong> (${score}). Valuations stretched, leverage rising — reduce exposure and beware black swans.</span>`);
  }

  // Sub-indicator highlights (top 2 extremes)
  const high = (indicators || []).filter(i => i.score >= 75).sort((a, b) => b.score - a.score).slice(0, 2);
  const low  = (indicators || []).filter(i => i.score <= 35).sort((a, b) => a.score - b.score).slice(0, 2);

  if (high.length) {
    const names = high.map(i => `${i.icon}${i.name} ${i.nameEn}（${i.score}）`).join('、');
    lines.push(`目前最強貪婪訊號來自：${names}，顯示風險偏好依然旺盛。<br/><span class="tip-en">Strongest greed signals from the above — risk appetite remains elevated.</span>`);
  }
  if (low.length) {
    const names = low.map(i => `${i.icon}${i.name} ${i.nameEn}（${i.score}）`).join('、');
    lines.push(`同時需留意弱勢指標：${names}，暗示部分風險因子正在升溫。<br/><span class="tip-en">Watch the weak indicators above — some risk factors are heating up.</span>`);
  }

  return lines.join('<br/><br/>');
}

// ── SEMICIRCLE GAUGE ───────────────────────────────────────────────────────

function drawGauge(canvas, score) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H - 10;
  const R  = Math.min(cx, cy) - 16;
  const startAngle = Math.PI;
  const endAngle   = 2 * Math.PI;

  ctx.clearRect(0, 0, W, H);

  ctx.beginPath();
  ctx.arc(cx, cy, R, startAngle, endAngle);
  ctx.strokeStyle = 'rgba(255,255,255,0.07)';
  ctx.lineWidth = 22;
  ctx.lineCap = 'round';
  ctx.stroke();

  const zones = [
    { from: 0,  to: 20,  color: '#ef4444' },
    { from: 20, to: 40,  color: '#f97316' },
    { from: 40, to: 60,  color: '#eab308' },
    { from: 60, to: 80,  color: '#22c55e' },
    { from: 80, to: 100, color: '#3b82f6' },
  ];
  zones.forEach(z => {
    const a1 = startAngle + (z.from / 100) * Math.PI;
    const a2 = startAngle + (z.to   / 100) * Math.PI;
    ctx.beginPath();
    ctx.arc(cx, cy, R, a1, a2);
    ctx.strokeStyle = z.color + '55';
    ctx.lineWidth = 22;
    ctx.lineCap = 'butt';
    ctx.stroke();
  });

  const fillEnd = startAngle + (score / 100) * Math.PI;
  const grad = ctx.createLinearGradient(cx - R, cy, cx + R, cy);
  grad.addColorStop(0,   '#ef4444');
  grad.addColorStop(0.5, '#eab308');
  grad.addColorStop(1,   '#3b82f6');
  ctx.beginPath();
  ctx.arc(cx, cy, R, startAngle, fillEnd);
  ctx.strokeStyle = grad;
  ctx.lineWidth = 22;
  ctx.lineCap = 'round';
  ctx.stroke();

  const needleAngle = startAngle + (score / 100) * Math.PI;
  const nLen = R - 10;
  const nx = cx + nLen * Math.cos(needleAngle);
  const ny = cy + nLen * Math.sin(needleAngle);
  // Blade-style needle with gold-to-red gradient
  const needleGrad = ctx.createLinearGradient(cx, cy, nx, ny);
  needleGrad.addColorStop(0, '#f5c518');
  needleGrad.addColorStop(1, '#e53939');
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(nx, ny);
  ctx.strokeStyle = needleGrad;
  ctx.lineWidth = 3;
  ctx.lineCap = 'round';
  ctx.shadowColor = '#f5c518';
  ctx.shadowBlur = 12;
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Center hub with gold glow
  ctx.beginPath();
  ctx.arc(cx, cy, 8, 0, Math.PI * 2);
  ctx.fillStyle = '#f5c518';
  ctx.shadowColor = '#f5c518';
  ctx.shadowBlur = 20;
  ctx.fill();
  ctx.shadowBlur = 0;

  const ticks = [
    { val: 0,   label: '0' },
    { val: 50,  label: '50' },
    { val: 100, label: '100' },
  ];
  ctx.font = '700 11px JetBrains Mono, monospace';
  ctx.fillStyle = 'rgba(255,255,255,0.4)';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ticks.forEach(t => {
    const a  = startAngle + (t.val / 100) * Math.PI;
    const lx = cx + (R + 20) * Math.cos(a);
    const ly = cy + (R + 20) * Math.sin(a);
    ctx.fillText(t.label, lx, ly);
  });
}

// ── ANIMATED COUNTER ───────────────────────────────────────────────────────

function animateCounter(el, target, duration = 1400) {
  let start = null;
  function step(ts) {
    if (!start) start = ts;
    const prog = Math.min((ts - start) / duration, 1);
    const ease = 1 - Math.pow(1 - prog, 4);
    el.textContent = Math.round(ease * target);
    if (prog < 1) requestAnimationFrame(step);
    else el.textContent = target;
  }
  requestAnimationFrame(step);
}

// ── RENDER CARDS ───────────────────────────────────────────────────────────

function renderCards(indicators) {
  const grid = document.getElementById('cardsGrid');
  grid.innerHTML = '';

  indicators.forEach((ind, idx) => {
    const color = scoreColor(ind.score);
    const badge = statusBadge(ind.score);
    const card  = document.createElement('div');
    card.className = 'indicator-card';
    card.style.setProperty('--card-accent', color);
    card.style.animationDelay = `${idx * 60}ms`;

    card.innerHTML = `
      <div class="card-header">
        <span class="card-icon">${ind.icon}</span>
        <span class="card-weight">權重 Weight ${ind.weight}</span>
      </div>
      <div class="card-name">${ind.name} <span class="card-name-en">${ind.nameEn}</span></div>
      <div class="card-value" style="color:${color}" id="card-val-${ind.id}">–</div>
      <div class="card-sub">${ind.rawValue}</div>
      <div class="card-bar-track">
        <div class="card-bar-fill" id="card-bar-${ind.id}"
          style="width:0%;background:${color}"></div>
      </div>
      <span class="card-status" style="background:${badge.bg};color:${badge.color}">${badge.text}</span>
      <div style="font-size:0.65rem;color:var(--muted);margin-top:8px">📡 ${ind.source}</div>
    `;
    grid.appendChild(card);

    setTimeout(() => {
      const valEl = document.getElementById(`card-val-${ind.id}`);
      animateCounter(valEl, ind.score, 1000);
      const barEl = document.getElementById(`card-bar-${ind.id}`);
      barEl.style.width = ind.score + '%';
    }, 300 + idx * 80);
  });
}

// ── WORLD MARKET MAP ──────────────────────────────────────────────────────

// Card direction overrides to prevent overlap in clustered regions
const CARD_DIRS = {
  spx:   '',             // US — default below
  dji:   'card-above',   // US — above to avoid S&P
  ixic:  'card-left',    // US — left edge
  ftse:  'card-left',    // Europe — left
  gdaxi: 'card-right',   // Europe — right
  fchi:  '',             // Europe — below (separated enough)
  n225:  'card-right',   // Japan — right edge
  kospi: 'card-above',   // Korea — above
  ssec:  'card-left',    // Shanghai — left
  twii:  'card-right',   // Taiwan — right
  hsi:   'card-left',    // HK — left to avoid Taiwan
  bsesn: 'card-left',    // India — left
  axjo:  'card-left',    // Australia — left
};

async function renderWorldMap() {
  const container = document.getElementById('worldMarkers');
  const loadingEl = document.getElementById('worldMapLoading');

  try {
    const resp = await fetch('/api/world-markets');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const { markets } = await resp.json();

    if (!markets || markets.length === 0) throw new Error('No data');

    container.innerHTML = '';

    markets.forEach(m => {
      const isUp = m.change_pct !== null && m.change_pct >= 0;
      const isNa = m.change_pct === null;
      const dotClass = isNa ? 'na' : (isUp ? 'up' : 'down');
      const chgClass = isNa ? 'na' : (isUp ? 'up' : 'down');
      const arrow = isNa ? '' : (isUp ? '▲' : '▼');
      const chgText = isNa ? 'N/A' : `${arrow} ${Math.abs(m.change_pct).toFixed(2)}%`;
      const cardDir = CARD_DIRS[m.id] || '';

      const marker = document.createElement('div');
      marker.className = 'world-marker';
      marker.style.left = m.x + '%';
      marker.style.top = m.y + '%';
      marker.tabIndex = 0; // for mobile tap focus

      marker.innerHTML = `
        <div class="marker-dot ${dotClass}"></div>
        <div class="marker-card ${cardDir}">
          <div class="marker-name">${m.name}</div>
          <div class="marker-price">${m.price}</div>
          <div class="marker-change ${chgClass}">${chgText}</div>
        </div>
      `;
      container.appendChild(marker);
    });

    loadingEl.classList.add('hidden');
    setTimeout(() => loadingEl.style.display = 'none', 400);

  } catch (err) {
    if (loadingEl) loadingEl.textContent = `⚠️ 全球市場載入失敗 ${err.message}`;
    console.error('World map error:', err);
  }
}

// ── SPX CANDLESTICK CHART ──────────────────────────────────────────────────

async function renderSpxChart() {
  const container = document.getElementById('spxChart');
  const loadingEl = document.getElementById('spxLoading');
  const titleEl   = document.getElementById('spxChartTitle');

  const w = container.parentElement.clientWidth;
  const h = container.parentElement.clientHeight;
  container.style.width  = w + 'px';
  container.style.height = h + 'px';

  const chart = LightweightCharts.createChart(container, {
    width: w, height: h,
    layout: { background: { color: '#0c1a2e' }, textColor: '#5a7a9e' },
    grid: {
      vertLines: { color: 'rgba(245,197,24,0.03)' },
      horzLines: { color: 'rgba(245,197,24,0.03)' },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: { color: 'rgba(245,197,24,0.25)', labelBackgroundColor: '#101e36' },
      horzLine: { color: 'rgba(245,197,24,0.25)', labelBackgroundColor: '#101e36' },
    },
    rightPriceScale: { borderColor: 'rgba(245,197,24,0.08)' },
    timeScale: { borderColor: 'rgba(245,197,24,0.08)', timeVisible: true },
    handleScroll: { mouseWheel: true, pressedMouseMove: true },
    handleScale:  { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
  });

  const candleSeries = chart.addCandlestickSeries({
    upColor: '#22c55e', downColor: '#ef4444',
    borderUpColor: '#22c55e', borderDownColor: '#ef4444',
    wickUpColor:   '#22c55e', wickDownColor:   '#ef4444',
  });

  new ResizeObserver(() => {
    chart.applyOptions({
      width:  container.parentElement.clientWidth,
      height: container.parentElement.clientHeight,
    });
  }).observe(container.parentElement);

  try {
    const resp = await fetch('/api/spx-klines?period=max');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const { candles, total } = await resp.json();
    candleSeries.setData(candles);
    chart.timeScale().fitContent();
    if (titleEl && total) {
      const firstYear = candles[0]?.time?.slice(0, 4) || '';
      titleEl.querySelector('span').textContent =
        `S&P 500 Daily Candlestick · ${total.toLocaleString()} bars (${firstYear}–now)`;
    }
    loadingEl.classList.add('hidden');
    setTimeout(() => loadingEl.style.display = 'none', 500);
  } catch (err) {
    loadingEl.textContent = `⚠️ 無法載入 SPX 資料：${err.message}`;
  }
}


// ── GAUGE ANIMATION ────────────────────────────────────────────────────────

function animateGauge(canvas, scoreEl, labelEl, glowEl, target, indicators) {
  const color = scoreColor(target);
  const lbl   = scoreLabel(target);

  scoreEl.style.color = color;
  labelEl.style.color = color;
  glowEl.style.boxShadow = `0 0 80px 20px ${color}30`;

  // Update commentary
  const commentaryEl = document.getElementById('commentaryBody');
  if (commentaryEl) {
    commentaryEl.innerHTML = generateCommentary(target, indicators);
  }
  const commentaryCard = document.getElementById('commentaryCard');
  if (commentaryCard) {
    commentaryCard.style.borderLeftColor = color;
  }

  const duration = 1600;
  let start = null;
  function step(ts) {
    if (!start) start = ts;
    const prog = Math.min((ts - start) / duration, 1);
    const ease = 1 - Math.pow(1 - prog, 4);
    const cur  = Math.round(ease * target);
    drawGauge(canvas, cur);
    scoreEl.textContent = cur;
    if (prog < 1) requestAnimationFrame(step);
    else {
      drawGauge(canvas, target);
      scoreEl.textContent = target;
      labelEl.innerHTML = `${lbl.zh} <span style="font-size:0.65rem;opacity:0.6;letter-spacing:1px">${lbl.en}</span>`;
    }
  }
  labelEl.innerHTML = `${lbl.zh} <span style="font-size:0.65rem;opacity:0.6;letter-spacing:1px">${lbl.en}</span>`;
  requestAnimationFrame(step);
}

// ── INIT ───────────────────────────────────────────────────────────────────

async function init() {
  const canvas  = document.getElementById('gaugeCanvas');
  const scoreEl = document.getElementById('gaugeScore');
  const labelEl = document.getElementById('gaugeLabel');
  const glowEl  = document.getElementById('gaugeGlow');
  const updateEl = document.getElementById('lastUpdate');

  // Draw empty gauge while loading
  drawGauge(canvas, 0);

  // ── Fetch real Blade God Index score ──
  try {
    const resp = await fetch('/api/blade-index');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (data.error) throw new Error(data.error);

    const score      = data.score;
    const indicators = data.indicators || [];

    // Update timestamp
    if (data.updatedAt) {
      const dt = new Date(data.updatedAt);
      updateEl.textContent = `最後更新 Updated：${dt.toLocaleDateString('zh-TW')} ${dt.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })}`;
    }

    animateGauge(canvas, scoreEl, labelEl, glowEl, Math.round(score), indicators);
    renderCards(indicators);

  } catch (err) {
    console.error('API error:', err);
    // Fallback to mock if API unavailable
    const FALLBACK_SCORE = 50;
    updateEl.textContent = '⚠️ 資料載入失敗，顯示模擬值';
    animateGauge(canvas, scoreEl, labelEl, glowEl, FALLBACK_SCORE, []);
    renderCards([]);
  }

  // ── Charts & map (independent, run in parallel) ──
  renderWorldMap();
  renderSpxChart();
}

document.addEventListener('DOMContentLoaded', init);
