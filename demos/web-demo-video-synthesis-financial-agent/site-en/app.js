function clamp01(x) {
  return Math.max(0, Math.min(1, x));
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = String(text);
}

function setBar(id, pct) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.width = `${Math.round(pct)}%`;
}

function allocFromRisk(risk01) {
  // 纯示意：风险偏好越高，Equity 权重越高，Cash 越低；Rates/Credit 做平衡项。
  const equity = 0.18 + 0.62 * risk01;
  const cash = 0.28 - 0.22 * risk01;
  const credit = 0.22 + 0.1 * Math.sin(risk01 * Math.PI);
  const rates = 1 - equity - cash - credit;
  return {
    equity: clamp01(equity),
    rates: clamp01(rates),
    credit: clamp01(credit),
    cash: clamp01(cash),
  };
}

function renderAlloc(risk) {
  const risk01 = clamp01(risk / 100);
  const a = allocFromRisk(risk01);
  setText("riskVal", risk);

  const toPct = (x) => `${Math.round(x * 100)}%`;
  setText("valEq", toPct(a.equity));
  setText("valRt", toPct(a.rates));
  setText("valCr", toPct(a.credit));
  setText("valCa", toPct(a.cash));

  setBar("barEq", a.equity * 100);
  setBar("barRt", a.rates * 100);
  setBar("barCr", a.credit * 100);
  setBar("barCa", a.cash * 100);

  return a;
}

function drawChart(canvas, alloc, t) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  ctx.globalAlpha = 1;
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 1;
  for (let i = 1; i <= 5; i += 1) {
    const y = Math.round((h * i) / 6);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  const center = h * 0.55;
  const amp = 26 + 34 * alloc.equity;
  const drift = (alloc.equity - alloc.rates) * 14;

  ctx.fillStyle = "rgba(48,255,205,0.10)";
  ctx.beginPath();
  for (let x = 0; x <= w; x += 8) {
    const px = x / w;
    const y = center - drift * px - Math.sin(px * 6.2 + t * 0.002) * amp * 0.45;
    const band = 14 + 10 * alloc.credit;
    if (x === 0) ctx.moveTo(x, y - band);
    else ctx.lineTo(x, y - band);
  }
  for (let x = w; x >= 0; x -= 8) {
    const px = x / w;
    const y = center - drift * px - Math.sin(px * 6.2 + t * 0.002) * amp * 0.45;
    const band = 14 + 10 * alloc.credit;
    ctx.lineTo(x, y + band);
  }
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = "rgba(48,255,205,0.86)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let x = 0; x <= w; x += 6) {
    const px = x / w;
    const y = center - drift * px - Math.sin(px * 6.2 + t * 0.002) * amp * 0.45;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function main() {
  const risk = document.getElementById("risk");
  const canvas = document.getElementById("chart");
  if (!risk || !canvas) return;

  let alloc = renderAlloc(Number(risk.value));
  risk.addEventListener("input", () => {
    alloc = renderAlloc(Number(risk.value));
  });

  const tick = (t) => {
    drawChart(canvas, alloc, t);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

main();

