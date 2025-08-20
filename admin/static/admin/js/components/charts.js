
// export function drawLineChart(canvas, data) {
//   const ctx = canvas.getContext('2d');
//   const width = canvas.width, height = canvas.height;
//   ctx.clearRect(0, 0, width, height);

//   const padding = 40;
//   const w = width - padding * 2;
//   const h = height - padding * 2;
//   const max = Math.max(...data), min = Math.min(...data);
//   const range = Math.max(1, max - min);

//   // grid
//   ctx.strokeStyle = 'rgba(255,140,66,0.1)';
//   ctx.lineWidth = 1;
//   for (let i = 0; i <= 5; i++) {
//     const y = padding + (h / 5) * i;
//     ctx.beginPath(); ctx.moveTo(padding, y); ctx.lineTo(width - padding, y); ctx.stroke();
//   }
//   for (let i = 0; i < data.length; i++) {
//     const x = padding + (w / (data.length - 1)) * i;
//     ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, height - padding); ctx.stroke();
//   }

//   // line
//   ctx.strokeStyle = '#00FFE0';
//   ctx.lineWidth = 3;
//   ctx.beginPath();
//   data.forEach((v, i) => {
//     const x = padding + (w / (data.length - 1)) * i;
//     const y = height - padding - ((v - min) / range) * h;
//     i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
//   });
//   ctx.stroke();

//   // area
//   ctx.fillStyle = 'rgba(0,255,224,0.1)';
//   ctx.lineTo(width - padding, height - padding);
//   ctx.lineTo(padding, height - padding);
//   ctx.closePath(); ctx.fill();

//   // points
//   ctx.fillStyle = '#00FFE0';
//   data.forEach((v, i) => {
//     const x = padding + (w / (data.length - 1)) * i;
//     const y = height - padding - ((v - min) / range) * h;
//     ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
//   });
// }

// export function drawBarChart(canvas, data) {
//   const ctx = canvas.getContext('2d');
//   const width = canvas.width, height = canvas.height;
//   ctx.clearRect(0,0,width,height);
//   const padding = 40;
//   const w = width - padding * 2;
//   const h = height - padding * 2;
//   const max = Math.max(...data);
//   const bw = (w / data.length) * 0.8;
//   const gap = (w / data.length) * 0.2;

//   data.forEach((v, i) => {
//     const bh = (v / max) * h;
//     const x = padding + i * (bw + gap) + gap / 2;
//     const y = height - padding - bh;
//     const g = ctx.createLinearGradient(0, y, 0, y + bh);
//     g.addColorStop(0, '#FF8C42'); g.addColorStop(1, 'rgba(255,140,66,0.3)');
//     ctx.fillStyle = g; ctx.fillRect(x, y, bw, bh);
//     ctx.strokeStyle = '#FF8C42'; ctx.lineWidth = 1; ctx.strokeRect(x, y, bw, bh);
//   });
// }






// --- safe helpers ---
function safeRange(min, max) {
  if (!isFinite(min) || !isFinite(max)) return { min: 0, max: 1, range: 1 };
  const r = max - min;
  return { min, max, range: r === 0 ? 1 : r }; // avoid zero range
}

function drawGrid(ctx, width, height, padding, vLines = 5, hSteps = 5) {
  const w = width - padding * 2;
  const h = height - padding * 2;
  ctx.strokeStyle = 'rgba(255,140,66,0.1)';
  ctx.lineWidth = 1;

  // horizontal grid
  for (let i = 0; i <= hSteps; i++) {
    const y = padding + (h / hSteps) * i;
    ctx.beginPath(); ctx.moveTo(padding, y); ctx.lineTo(width - padding, y); ctx.stroke();
  }
  // vertical grid (only if we have multiple x-steps)
  const denom = Math.max(1, vLines);
  for (let i = 0; i <= vLines; i++) {
    const x = padding + (w / denom) * i;
    ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, height - padding); ctx.stroke();
  }
}

export function drawLineChart(canvas, data) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width, height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const padding = 40;
  const w = width - padding * 2;
  const h = height - padding * 2;

  const arr = Array.isArray(data) ? data : [];
  if (arr.length === 0) {
    drawGrid(ctx, width, height, padding, 5, 5);
    return; // nothing else to draw
  }

  const { min, max, range } = safeRange(Math.min(...arr), Math.max(...arr));
  const denom = Math.max(1, arr.length - 1); // avoid divide-by-zero for single point

  // grid (use data length for vertical guides when >1)
  drawGrid(ctx, width, height, padding, arr.length > 1 ? arr.length - 1 : 5, 5);

  // line path
  ctx.strokeStyle = '#00FFE0';
  ctx.lineWidth = 3;
  ctx.beginPath();
  for (let i = 0; i < arr.length; i++) {
    const x = padding + (w / denom) * i;
    const y = height - padding - ((arr[i] - min) / range) * h;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // area fill (only if we have at least 2 points to form a polygon)
  if (arr.length >= 2) {
    const lastX = padding + (w / denom) * (arr.length - 1);
    ctx.fillStyle = 'rgba(0,255,224,0.1)';
    ctx.lineTo(lastX, height - padding);
    ctx.lineTo(padding, height - padding);
    ctx.closePath();
    ctx.fill();
  }

  // points
  ctx.fillStyle = '#00FFE0';
  for (let i = 0; i < arr.length; i++) {
    const x = padding + (w / denom) * i;
    const y = height - padding - ((arr[i] - min) / range) * h;
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
  }
}

export function drawBarChart(canvas, data) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width, height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const padding = 40;
  const w = width - padding * 2;
  const h = height - padding * 2;

  const arr = Array.isArray(data) ? data : [];
  if (arr.length === 0) {
    drawGrid(ctx, width, height, padding, 5, 5);
    return;
  }

  // prevent division by zero when all values are 0
  const maxVal = Math.max(1, ...arr);
  const bw = (w / arr.length) * 0.8;
  const gap = (w / arr.length) * 0.2;

  // light grid in background
  drawGrid(ctx, width, height, padding, arr.length, 5);

  for (let i = 0; i < arr.length; i++) {
    const v = arr[i];
    const bh = (v / maxVal) * h;               // 0 when v==0 (ok)
    const x = padding + i * (bw + gap) + gap / 2;
    const y = height - padding - bh;

    const g = ctx.createLinearGradient(0, y, 0, y + Math.max(1, bh));
    g.addColorStop(0, '#FF8C42'); g.addColorStop(1, 'rgba(255,140,66,0.3)');
    ctx.fillStyle = g;
    ctx.fillRect(x, y, bw, Math.max(1, bh));   // ensure at least 1px so it’s visible on tiny values
    ctx.strokeStyle = '#FF8C42';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, bw, Math.max(1, bh));
  }
}
