
export function drawLineChart(canvas, data) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width, height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const padding = 40;
  const w = width - padding * 2;
  const h = height - padding * 2;
  const max = Math.max(...data), min = Math.min(...data);
  const range = Math.max(1, max - min);

  // grid
  ctx.strokeStyle = 'rgba(255,140,66,0.1)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) {
    const y = padding + (h / 5) * i;
    ctx.beginPath(); ctx.moveTo(padding, y); ctx.lineTo(width - padding, y); ctx.stroke();
  }
  for (let i = 0; i < data.length; i++) {
    const x = padding + (w / (data.length - 1)) * i;
    ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, height - padding); ctx.stroke();
  }

  // line
  ctx.strokeStyle = '#00FFE0';
  ctx.lineWidth = 3;
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = padding + (w / (data.length - 1)) * i;
    const y = height - padding - ((v - min) / range) * h;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();

  // area
  ctx.fillStyle = 'rgba(0,255,224,0.1)';
  ctx.lineTo(width - padding, height - padding);
  ctx.lineTo(padding, height - padding);
  ctx.closePath(); ctx.fill();

  // points
  ctx.fillStyle = '#00FFE0';
  data.forEach((v, i) => {
    const x = padding + (w / (data.length - 1)) * i;
    const y = height - padding - ((v - min) / range) * h;
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
  });
}

export function drawBarChart(canvas, data) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width, height = canvas.height;
  ctx.clearRect(0,0,width,height);
  const padding = 40;
  const w = width - padding * 2;
  const h = height - padding * 2;
  const max = Math.max(...data);
  const bw = (w / data.length) * 0.8;
  const gap = (w / data.length) * 0.2;

  data.forEach((v, i) => {
    const bh = (v / max) * h;
    const x = padding + i * (bw + gap) + gap / 2;
    const y = height - padding - bh;
    const g = ctx.createLinearGradient(0, y, 0, y + bh);
    g.addColorStop(0, '#FF8C42'); g.addColorStop(1, 'rgba(255,140,66,0.3)');
    ctx.fillStyle = g; ctx.fillRect(x, y, bw, bh);
    ctx.strokeStyle = '#FF8C42'; ctx.lineWidth = 1; ctx.strokeRect(x, y, bw, bh);
  });
}
