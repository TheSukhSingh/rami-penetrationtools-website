
// --- helpers ---------------------------------------------------------------
function safeRange(min, max) {
  if (!isFinite(min) || !isFinite(max)) return { min: 0, max: 1, range: 1 };
  const r = max - min;
  return { min, max, range: r === 0 ? 1 : r };
}

// Fit canvas to its parent width + desired CSS height, and scale for DPR
function prepCanvas(canvas, cssHeight = 260) {
  const dpr = window.devicePixelRatio || 1;
  const parent = canvas.parentElement;
  const cssWidth = Math.max(300, (parent?.clientWidth || canvas.clientWidth || canvas.width || 900));

  // CSS size
  canvas.style.display = 'block';
  canvas.style.width = '100%';
  canvas.style.height = cssHeight + 'px';

  // Backing store size (device pixels)
  canvas.width  = Math.round(cssWidth * dpr);
  canvas.height = Math.round(cssHeight * dpr);

  const ctx = canvas.getContext('2d');
  // Draw using CSS pixels; scale context to hide DPR complexity
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  // Return logical (CSS) width/height for drawing math
  return { ctx, width: cssWidth, height: cssHeight };
}

function drawGrid(ctx, width, height, padding, vLines = 5, hSteps = 5) {
  const w = width - padding * 2;
  const h = height - padding * 2;
  ctx.strokeStyle = 'rgba(255,140,66,0.1)';
  ctx.lineWidth = 1;

  for (let i = 0; i <= hSteps; i++) {
    const y = padding + (h / hSteps) * i;
    ctx.beginPath(); ctx.moveTo(padding, y); ctx.lineTo(width - padding, y); ctx.stroke();
  }
  const denom = Math.max(1, vLines);
  for (let i = 0; i <= vLines; i++) {
    const x = padding + (w / denom) * i;
    ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, height - padding); ctx.stroke();
  }
}

// --- line -------------------------------------------------------------------
export function drawLineChart(canvas, data) {
  const { ctx, width, height } = prepCanvas(canvas, 320);
  ctx.clearRect(0, 0, width, height);

  const padding = 40;
  const w = width - padding * 2;
  const h = height - padding * 2;

  const arr = Array.isArray(data) ? data : [];
  if (arr.length === 0) {
    drawGrid(ctx, width, height, padding, 5, 5);
    return;
  }

  const { min, max, range } = safeRange(Math.min(...arr), Math.max(...arr));
  const denom = Math.max(1, arr.length - 1);

  drawGrid(ctx, width, height, padding, arr.length > 1 ? arr.length - 1 : 5, 5);

  ctx.strokeStyle = '#00FFE0';
  ctx.lineWidth = 3;
  ctx.beginPath();
  for (let i = 0; i < arr.length; i++) {
    const x = padding + (w / denom) * i;
    const y = height - padding - ((arr[i] - min) / range) * h;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  if (arr.length >= 2) {
    const lastX = padding + (w / denom) * (arr.length - 1);
    ctx.fillStyle = 'rgba(0,255,224,0.1)';
    ctx.lineTo(lastX, height - padding);
    ctx.lineTo(padding, height - padding);
    ctx.closePath();
    ctx.fill();
  }

  ctx.fillStyle = '#00FFE0';
  for (let i = 0; i < arr.length; i++) {
    const x = padding + (w / denom) * i;
    const y = height - padding - ((arr[i] - min) / range) * h;
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
  }
}

// --- bars -------------------------------------------------------------------
export function drawBarChart(canvas, data) {
  const { ctx, width, height } = prepCanvas(canvas, 320);
  ctx.clearRect(0, 0, width, height);

  const padding = 40;
  const w = width - padding * 2;
  const h = height - padding * 2;

  const arr = Array.isArray(data) ? data : [];
  if (arr.length === 0) {
    drawGrid(ctx, width, height, padding, 5, 5);
    return;
  }

  const maxVal = Math.max(1, ...arr);
  const bw = (w / arr.length) * 0.8;
  const gap = (w / arr.length) * 0.2;

  drawGrid(ctx, width, height, padding, arr.length, 5);

  for (let i = 0; i < arr.length; i++) {
    const v = arr[i];
    const bh = (v / maxVal) * h;
    const x = padding + i * (bw + gap) + gap / 2;
    const y = height - padding - bh;

    const g = ctx.createLinearGradient(0, y, 0, y + Math.max(1, bh));
    g.addColorStop(0, '#FF8C42'); g.addColorStop(1, 'rgba(255,140,66,0.3)');
    ctx.fillStyle = g;
    ctx.fillRect(x, y, bw, Math.max(1, bh));
    ctx.strokeStyle = '#FF8C42';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, bw, Math.max(1, bh));
  }
}



// ====== nice axis ticks ======
function niceStep(max, ticks = 5) {
  const raw = Math.max(1e-9, max) / ticks;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const frac = raw / pow;
  const niceFrac = frac < 1.5 ? 1 : frac < 3 ? 2 : frac < 7 ? 5 : 10;
  return niceFrac * pow;
}
function formatK(n){ if (n >= 1e6) return (n/1e6).toFixed(1).replace(/\.0$/,'')+'M';
                    if (n >= 1e3) return (n/1e3).toFixed(1).replace(/\.0$/,'')+'k';
                    return String(n); }

// ====== tooltip element ======
function ensureTip(container){
  let tip = container.querySelector('.chart-tip');
  if (!tip) {
    tip = document.createElement('div');
    tip.className = 'chart-tip';
    tip.style.position = 'absolute';
    tip.style.pointerEvents = 'none';
    tip.style.padding = '6px 8px';
    tip.style.font = '12px/1.2 system-ui, sans-serif';
    tip.style.background = 'rgba(0,0,0,0.8)';
    tip.style.border = '1px solid rgba(255,140,66,0.5)';
    tip.style.borderRadius = '8px';
    tip.style.color = '#fff';
    tip.style.transform = 'translate(-50%, -120%)';
    tip.style.whiteSpace = 'nowrap';
    tip.style.display = 'none';
    container.style.position = 'relative';
    container.appendChild(tip);
  }
  return tip;
}

// ====== time-series with axes + hover ======
export function drawTimeSeriesChart(canvas, points, opts = {}) {
  const { ctx, width, height } = prepCanvas(canvas, 320);     // you already have prepCanvas
  const paddingLeft = 50, paddingRight = 16, paddingTop = 16, paddingBottom = 34;
  ctx.clearRect(0, 0, width, height);

  if (!Array.isArray(points) || points.length === 0) return;

  // domains
  const xs = points.map(p => +p.x);
  const ys = points.map(p => +p.y);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMax = Math.max(1, Math.max(...ys));
  const step = niceStep(yMax, 5);
  const yAxisMax = Math.ceil(yMax / step) * step;

  const plotW = width - paddingLeft - paddingRight;
  const plotH = height - paddingTop - paddingBottom;

  // axis helpers
  const xScale = (t) => paddingLeft + ((t - xMin) / Math.max(1, xMax - xMin)) * plotW;
  const yScale = (v) => paddingTop + (1 - (v / Math.max(1, yAxisMax))) * plotH;

  // grid + axes
  ctx.strokeStyle = 'rgba(255,140,66,0.12)';
  ctx.lineWidth = 1;

  // y grid
  for (let y = 0; y <= yAxisMax + 1e-6; y += step) {
    const yy = yScale(y);
    ctx.beginPath(); ctx.moveTo(paddingLeft, yy); ctx.lineTo(width - paddingRight, yy); ctx.stroke();
    // labels
    ctx.fillStyle = 'rgba(255,255,255,0.7)';
    ctx.font = '12px system-ui, sans-serif';
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    ctx.fillText(formatK(y), paddingLeft - 8, yy);
  }

  // x ticks: ~6 labels
  const tickCount = Math.max(2, Math.min(6, points.length));
  const stepIdx = Math.max(1, Math.floor(points.length / tickCount));
  ctx.fillStyle = 'rgba(255,255,255,0.7)';
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  for (let i = 0; i < points.length; i += stepIdx) {
    const t = +points[i].x, x = xScale(t);
    ctx.beginPath(); ctx.moveTo(x, height - paddingBottom); ctx.lineTo(x, height - paddingBottom + 6); ctx.stroke();
    const d = new Date(t);
    const label = (opts.bucket === 'month')
      ? d.toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
      : (opts.bucket === 'week')
        ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    ctx.fillText(label, x, height - paddingBottom + 8);
  }

  // line + area
  ctx.strokeStyle = '#00FFE0';
  ctx.lineWidth = 3;
  ctx.beginPath();
  points.forEach((p, i) => {
    const x = xScale(+p.x), y = yScale(+p.y);
    if (!i) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  });
  ctx.stroke();

  if (points.length >= 2) {
    ctx.lineTo(xScale(+points.at(-1).x), height - paddingBottom);
    ctx.lineTo(xScale(+points[0].x), height - paddingBottom);
    ctx.closePath();
    ctx.fillStyle = 'rgba(0,255,224,0.10)';
    ctx.fill();
  }

  // interactive hover
  const container = canvas.parentElement;
  const tip = ensureTip(container);
  function handleMove(evt){
    const rect = canvas.getBoundingClientRect();
    const mx = evt.clientX - rect.left;
    // find nearest index by x
    let bestI = 0, bestDX = Infinity;
    for (let i=0; i<points.length; i++){
      const dx = Math.abs(xScale(+points[i].x) - mx);
      if (dx < bestDX){ bestDX = dx; bestI = i; }
    }
    const p = points[bestI];
    const x = xScale(+p.x), y = yScale(+p.y);

    // redraw overlay
    ctx.save();
    ctx.clearRect(0, 0, width, height);
    drawTimeSeriesChart(canvas, points, opts); // base
    ctx.restore();

    // guide
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, paddingTop); ctx.lineTo(x, height - paddingBottom); ctx.stroke();

    // point
    ctx.fillStyle = '#00FFE0';
    ctx.beginPath(); ctx.arc(x,y,4,0,Math.PI*2); ctx.fill();

    // tooltip
    tip.style.display = 'block';
    tip.style.left = `${x}px`;
    tip.style.top  = `${y}px`;
    const d = new Date(+p.x);
    const df = (opts.bucket === 'month')
      ? d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
      : d.toLocaleDateString(undefined, { weekday:'short', month:'short', day:'numeric' });
    tip.innerHTML = `<b>${df}</b><br>${formatK(p.y)} scans`;
  }
  function handleLeave(){ tip.style.display = 'none'; drawTimeSeriesChart(canvas, points, opts); }

  canvas.onmousemove = handleMove;
  canvas.onmouseleave = handleLeave;
}

// ====== bars with labels + hover ======
export function drawBarChartLabeled(canvas, labels, values) {
  const { ctx, width, height } = prepCanvas(canvas, 320);
  ctx.clearRect(0,0,width,height);
  const padding = 50, bottom = 40, right = 16, top = 16;
  const plotW = width - padding - right, plotH = height - top - bottom;

  const n = Math.max(1, values.length);
  const maxVal = Math.max(1, ...values);
  const step = niceStep(maxVal, 5);
  const yAxisMax = Math.ceil(maxVal / step) * step;

  // y grid + labels
  ctx.strokeStyle = 'rgba(255,140,66,0.12)';
  ctx.lineWidth = 1;
  for (let y=0; y<=yAxisMax+1e-6; y+=step){
    const yy = top + (1 - y / yAxisMax) * plotH;
    ctx.beginPath(); ctx.moveTo(padding, yy); ctx.lineTo(width - right, yy); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.textAlign='right'; ctx.textBaseline='middle'; ctx.font='12px system-ui';
    ctx.fillText(formatK(y), padding - 8, yy);
  }

  const bw = plotW / n * 0.8;
  const gap = plotW / n * 0.2;

  // x labels + bars
  const bars = [];
  labels.forEach((lbl, i) => {
    const v = values[i] ?? 0;
    const bh = (v / yAxisMax) * plotH;
    const x = padding + i * (bw + gap) + gap/2;
    const y = top + (plotH - bh);

    const g = ctx.createLinearGradient(0, y, 0, y + Math.max(1, bh));
    g.addColorStop(0, '#FF8C42'); g.addColorStop(1, 'rgba(255,140,66,0.3)');
    ctx.fillStyle = g; ctx.fillRect(x, y, bw, Math.max(1, bh));
    ctx.strokeStyle = '#FF8C42'; ctx.lineWidth = 1; ctx.strokeRect(x, y, bw, Math.max(1, bh));

    // x labels
    ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.textAlign='center'; ctx.textBaseline='top';
    ctx.save();
    // truncate long names
    const L = (lbl ?? '').toString();
    const short = L.length > 8 ? L.slice(0,8)+'…' : L;
    ctx.fillText(short, x + bw/2, height - bottom + 8);
    ctx.restore();

    bars.push({x, y, w: bw, h: Math.max(1,bh), label: L, value: v});
  });

  // hover tooltip
  const tip = ensureTip(canvas.parentElement);
  canvas.onmousemove = (e)=>{
    const r = canvas.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const hit = bars.find(b => mx >= b.x && mx <= b.x+b.w && my >= b.y && my <= b.y+b.h);
    if (!hit){ tip.style.display='none'; return; }
    tip.style.display='block';
    tip.style.left = (hit.x + hit.w/2) + 'px';
    tip.style.top  = (hit.y) + 'px';
    tip.innerHTML = `<b>${hit.label || 'Tool'}</b><br>${formatK(hit.value)} uses`;
  };
  canvas.onmouseleave = () => tip.style.display='none';
}
