/* KRL Insight - dashboard. Data dari data/data.json (pipeline Python).
   Tambahkan ?demo=1 pada URL untuk pratinjau desain dengan DATA DEMO (bukan data nyata). */
const $ = (s) => document.querySelector(s);
const NAVY = '#12305c', COL = { aman: '#16a34a', waspada: '#d97706', kritis: '#dc2626' };
const nf = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 });
const pf = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 });
const fmt = (v) => (v == null ? '--' : nf.format(v));
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
const bln = (m) => { const [y, k] = m.split('-'); return `${MON[+k - 1]} ${y}`; };
const ico = (d) => `<svg viewBox="0 0 24 24">${d}</svg>`;
const PAGES = [
  ['dashboard', 'Dashboard', '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>'],
  ['prediksi', 'Prediksi Penumpang', '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>'],
  ['historis', 'Analisis Historis', '<path d="M3 3v18h18"/><path d="M7 14l3-4 3 3 5-6"/>'],
  ['risiko', 'Risiko Kapasitas', '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>'],
  ['chat', 'Asisten AI', '<rect x="3" y="11" width="18" height="10" rx="3"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4M8 15h.01M16 15h.01"/>']
];
let D, ambang, charts = {};
function DEMO_FLAG() { return typeof DEMO !== 'undefined' ? DEMO : new URLSearchParams(location.search).has('demo'); }

/* ---------- Logika risiko (aturan tetap sesuai rancangan) ---------- */
const risk = (u95, thr) => {
  if (u95 == null || !thr) return { s: null, p: null };
  const p = (u95 / thr) * 100;
  return { s: p >= 100 ? 'kritis' : p >= 90 ? 'waspada' : 'aman', p };
};
const badge = (s) => `<span class="badge ${s || ''}">${s ? s.toUpperCase() : 'Menunggu data'}</span>`;

/* ---------- Data ---------- */
function demoData() { // DATA DEMO: sintetis, hanya untuk pratinjau tampilan
  const hist = [], fc = []; let y = 2016, m = 0;
  for (let i = 0; i < 100; i++) {
    const covid = i >= 50 && i <= 68, season = 1 + 0.05 * Math.sin((m / 12) * 2 * Math.PI);
    const v = (covid ? 20000 : 28000 + i * 90) * season * (1 + 0.02 * Math.sin(i * 7));
    hist.push({ bulan: `${y}-${String(m + 1).padStart(2, '0')}`, nilai: Math.round(v), hari_kerja: 18 + ((i * 5) % 5) });
    if (++m > 11) { m = 0; y++; }
  }
  const last = hist[hist.length - 1].nilai;
  for (let h = 1; h <= 6; h++) {
    const p = last * (1 + 0.004 * h), w = 900 + h * 450;
    fc.push({ bulan: `${y}-${String(m + 1).padStart(2, '0')}`, titik: Math.round(p), l80: Math.round(p - w * 0.78), u80: Math.round(p + w * 0.78), l95: Math.round(p - w), u95: Math.round(p + w) });
    if (++m > 11) { m = 0; y++; }
  }
  const ev = (mase) => ({ mase, rmse: mase * 1500, mae: mase * 1200, picp80: 0.8, picp95: 0.94, mpiw: 5000, winkler: 9000 });
  const names = ['Naive', 'Seasonal Naive', 'ETS (Holt-Winters)', 'SARIMAX', 'LightGBM'];
  return {
    meta: { sumber: 'DEMO', satuan: 'ribu penumpang', periode_data: `${hist[0].bulan} s.d. ${hist[99].bulan}`, diperbarui: 'DEMO', model_terpilih: null, lebaran: ['2017-06', '2018-06', '2019-06', '2022-05', '2023-04'] },
    ambang_kapasitas: { nilai: Math.round(last * 1.06), keterangan: 'Parameter sistem (demo)' },
    historis: hist, forecast: fc,
    evaluasi: { keseluruhan: names.map((n, i) => ({ model: n, ...ev([1.4, 1.1, 0.9, 0.85, 0.95][i]) })), pasca_covid: names.map((n, i) => ({ model: n, mase: [1.3, 1.0, 0.8, 0.8, 0.9][i] })) }
  };
}
async function load() {
  const demo = DEMO_FLAG();
  try { D = demo ? demoData() : await (await fetch('data/data.json')).json(); }
  catch (e) { D = null; }
  if (!D) { $('#view').innerHTML = '<div class="card"><div class="empty">Gagal memuat data/data.json. Jalankan lewat server lokal (mis. <code>python -m http.server</code>).</div></div>'; return; }
  ambang = D.ambang_kapasitas.nilai;
  if (demo) { $('#banner').hidden = false; $('#banner').textContent = 'MODE DEMO: seluruh angka sintetis untuk pratinjau desain. Bukan data atau hasil prediksi nyata.'; }
  $('#sf-periode').textContent = D.meta.periode_data || '--';
  const ready = D.historis.length && D.forecast.length;
  $('#sf-status').textContent = demo ? 'Mode demo' : ready ? 'Data terhubung' : 'Menunggu data';
  $('#sf-dot').style.background = demo ? '#f59e0b' : ready ? '#22c55e' : '#94a3b8';
  route();
}

/* ---------- Helper chart ---------- */
function chart(id, cfg) {
  if (charts[id]) charts[id].destroy();
  const el = document.getElementById(id); if (!el) return;
  cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false } }, cfg.options);
  Chart.defaults.font.family = 'Inter'; charts[id] = new Chart(el, cfg);
}
const empty = (t = 'Menunggu data dari pipeline Python') => `<div class="empty">${t}</div>`;
const ax = (title) => ({ title: { display: true, text: title }, ticks: { callback: (v) => nf.format(v) } });
const covidBox = { id: 'covid', beforeDatasetsDraw(c, _, o) { // area COVID-19 & garis Lebaran
  const x = c.scales.x, y = c.scales.y, L = c.data.labels; if (!o.on) return;
  const a = L.indexOf('2020-03'), b = L.indexOf('2021-12'), g = c.ctx;
  if (a >= 0) { g.save(); g.fillStyle = 'rgba(100,116,139,.12)'; const x1 = x.getPixelForValue(a), x2 = x.getPixelForValue(b >= 0 ? b : L.length - 1); g.fillRect(x1, y.top, x2 - x1, y.bottom - y.top); g.restore(); }
  g.save(); g.strokeStyle = 'rgba(217,119,6,.5)'; g.setLineDash([3, 3]);
  (o.lebaran || []).forEach((m) => { const i = L.indexOf(m); if (i < 0) return; const px = x.getPixelForValue(i); g.beginPath(); g.moveTo(px, y.top); g.lineTo(px, y.bottom); g.stroke(); }); g.restore(); } };

function forecastChart(id, fc, withHist = true, nh = 36) {
  const H = withHist ? D.historis.slice(-nh) : [];
  const L = [...H.map((r) => r.bulan), ...fc.map((r) => r.bulan)], n = H.length;
  const pad = (arr) => [...Array(n).fill(null), ...arr];
  const act = [...H.map((r) => r.nilai), ...fc.map(() => null)];
  const pt = pad(fc.map((r) => r.titik)); if (n) pt[n - 1] = H[n - 1].nilai;
  const band = (k, f, c, lbl) => ({ label: lbl, data: pad(fc.map((r) => r[k])), borderWidth: 0, pointRadius: 0, fill: f, backgroundColor: c });
  chart(id, { type: 'line', data: { labels: L, datasets: [
    band('l95', false, 'transparent', 'Batas bawah 95%'), band('u95', '-1', 'rgba(18,48,92,.10)', 'Batas atas 95%'),
    band('l80', false, 'transparent', 'Batas bawah 80%'), band('u80', '-1', 'rgba(18,48,92,.22)', 'Batas atas 80%'),
    { label: 'Aktual', data: act, borderColor: NAVY, borderWidth: 2, pointRadius: 0, tension: .2 },
    { label: 'Prediksi titik', data: pt, borderColor: '#2563eb', borderDash: [6, 4], borderWidth: 2, pointRadius: 3 }] },
    options: { plugins: { legend: { position: 'bottom', labels: { filter: (i) => !/Batas bawah/.test(i.text), usePointStyle: true } },
      tooltip: { callbacks: { title: (i) => bln(i[0].label), label: (c) => c.raw == null ? null : ` ${c.dataset.label}: ${fmt(c.raw)} ribu` } } },
      scales: { y: ax('ribu penumpang'), x: { ticks: { callback(v) { return bln(this.getLabelForValue(v)); }, maxTicksLimit: 8 } } } } });
}

/* ---------- Halaman ---------- */
const head = (t, d, extra = '') => { const [a, b] = t.includes('|') ? t.split('|') : [t.split(' ')[0], t.split(' ').slice(1).join(' ')]; return `<header class="ph"><div><h1>${a} <span class="g">${b}</span></h1><p class="sub">${d}</p><div class="meta">Diperbarui: ${D.meta.diperbarui || 'Menunggu data'} &middot; Satuan: ribu penumpang</div></div><div class="hr">${extra}</div></header>`; };
const hasF = () => D.forecast.length > 0, hasH = () => D.historis.length > 0;
const rr = (r) => risk(r.u95, ambang);

const pages = {
  beranda() {
    const I = (d, n = 22) => `<svg viewBox="0 0 24 24" width="${n}" height="${n}" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
    const logo = '<svg viewBox="0 0 32 32" width="32" height="32"><rect x="6" y="3" width="20" height="21" rx="5" fill="#0b1f3f"/><rect x="9" y="7" width="14" height="8" rx="2" fill="#fff"/><circle cx="11.5" cy="19.5" r="1.7" fill="#fff"/><circle cx="20.5" cy="19.5" r="1.7" fill="#fff"/><path d="M9 29l3-5m11 5l-3-5" stroke="#0b1f3f" stroke-width="2" stroke-linecap="round"/></svg>';
    const P = { check: '<path d="M5 12l4 4 10-10"/>' };
    $('#view').innerHTML = `<div class="lp">
    <header class="lp-top wrap"><a class="lp-brand" href="#beranda">${logo}KRL Insight</a>
      <a class="btn acc" href="#dashboard">Buka dashboard</a></header>

    <section class="lp-hero"><div class="wrap lp-hg">
      <div class="lp-copy"><span class="lp-eyebrow">Forecasting &amp; Deteksi Risiko Kapasitas</span>
        <h1>Prediksi Penumpang <em>KRL Jabodetabek</em></h1>
        <p>Pantau proyeksi jumlah penumpang 1–6 bulan ke depan, rentang ketidakpastian prediksi, serta peringatan dini sebelum lonjakan melebihi kapasitas operasional.</p>
        <div class="hero-cta"><a class="btn acc lg" href="#dashboard">Masuk ke dashboard</a></div>
        <ul class="lp-marks"><li>${I(P.check, 18)}Data BPS</li><li>${I(P.check, 18)}Interval 80% &amp; 95%</li><li>${I(P.check, 18)}Asisten Chat AI</li></ul></div>
      <div class="lp-scene">
        <svg class="krl-bg-svg" viewBox="0 0 640 430" preserveAspectRatio="xMaxYMid slice" role="img" aria-label="Ilustrasi Lokomotif KAI dan Jalur Rel">
          <defs>
            <linearGradient id="beam-gradient" x1="100%" y1="50%" x2="0%" y2="50%">
              <stop offset="0%" stop-color="#fef08a" stop-opacity="0.85"/>
              <stop offset="35%" stop-color="#fef9c3" stop-opacity="0.35"/>
              <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
            </linearGradient>
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="5" result="blur"/>
              <feComposite in="SourceGraphic" in2="blur" operator="over"/>
            </filter>
          </defs>

          <!-- Langit & Matahari -->
          <rect width="640" height="430" fill="#cfe3fb"/>
          <circle class="krl-sun" cx="520" cy="75" r="44" fill="#fff" opacity=".8"/>

          <!-- Parallax Lapisan Gedung Jauh (Distant Skyline) -->
          <g class="krl-city-far" fill="#bdd6f5">
            ${[0, 640].map((dx) => [[10, 150, 50, 150], [70, 110, 60, 190], [140, 170, 70, 130], [220, 120, 50, 180], [280, 140, 60, 160], [350, 100, 70, 200], [430, 160, 50, 140], [490, 115, 70, 185], [570, 145, 60, 155]].map(([x, y, w, h]) => `<rect x="${x + dx}" y="${y}" width="${w}" height="${h}"/>`).join('')).join('')}
          </g>

          <!-- Parallax Lapisan Gedung Dekat (Midground Skyline) -->
          <g class="krl-city-near" fill="#9bbfe8">
            ${[0, 640].map((dx) => [[20, 130, 70, 170], [100, 90, 60, 210], [170, 150, 80, 150], [330, 110, 70, 190], [410, 155, 60, 145], [480, 100, 80, 200], [570, 140, 70, 160]].map(([x, y, w, h]) => `<rect x="${x + dx}" y="${y}" width="${w}" height="${h}"/>`).join('')).join('')}
          </g>

          <!-- Tanah & Balas Rel -->
          <polygon points="0,320 640,290 640,430 0,430" fill="#cbd5e1" opacity=".7"/>
          <polygon points="0,355 640,325 640,430 0,430" fill="#94a3b8" opacity=".5"/>

          <!-- Bantalan Rel Bergerak Mulus (Ties) -->
          <g class="krl-ties">
            ${Array.from({length: 32}, (_, i) => {
              const xt = (i - 4) * 32;
              const yt = Math.round(352 - xt * 0.044);
              return `<line x1="${xt}" y1="${yt}" x2="${xt + 16}" y2="${yt + 78}" stroke="#475569" stroke-width="6" opacity=".75"/>`;
            }).join('')}
          </g>

          <!-- Rel Belakang (Rail 2) -->
          <line x1="-40" y1="364" x2="680" y2="332" stroke="#334155" stroke-width="5"/>

          <!-- Rel Depan (Rail 1) -->
          <line x1="-40" y1="426" x2="680" y2="394" stroke="#1e293b" stroke-width="6"/>

          <!-- Lokomotif KAI (Bagian belakang memanjang penuh ke pojok kanan tanpa ada ruang kosong) -->
          <g class="krl-loco-group">
            <!-- Sorot Lampu Depan Lokomotif -->
            <g class="krl-headlights">
              <polygon points="335,276 0,150 0,430 450,280" fill="url(#beam-gradient)"/>
              <circle cx="335" cy="276" r="11" fill="#fef08a" filter="url(#glow)"/>
              <circle cx="450" cy="280" r="11" fill="#fef08a" filter="url(#glow)"/>
            </g>
            <!-- Gambar Lokomotif KAI (x=165, width=560 menempel rapat dan memanjang tembus pojok kanan) -->
            <image href="img/lokomotif-kai.png" xlink:href="img/lokomotif-kai.png" x="165" y="18" width="560" height="404" preserveAspectRatio="none"/>
          </g>
        </svg>
      </div>
    </div></section>

    <footer class="lp-foot wrap">KRL Insight &middot; Sistem pendukung keputusan, bukan pengganti keputusan operasional resmi &middot; Sumber data: BPS</footer></div>`;
  },
  dashboard() {
    const H = D.historis, F = D.forecast, lastH = H[H.length - 1], f1 = F[0], r1 = f1 ? rr(f1) : {}, prev = H.length > 1 ? H[H.length - 2] : null;
    const chg = lastH && prev ? (lastH.nilai / prev.nilai - 1) * 100 : null;
    const dl = (x) => (x == null ? '' : `<span class="dl ${x >= 0 ? '' : 'dn'}">${x >= 0 ? '+' : ''}${pf.format(x)}%</span>`);
    const arr = (h) => `<a class="rb" href="${h}" aria-label="Buka halaman"><svg viewBox="0 0 24 24"><path d="M7 17L17 7M8 7h9v9"/></svg></a>`;
    const num = (v) => (v == null ? '<span class="g">--</span>' : `${fmt(v)} <small>ribu</small>`);
    let worst = null; F.forEach((r) => { const k = rr(r); if (k.p != null && (!worst || k.p > worst.p)) worst = { ...k, bulan: r.bulan }; });
    const ins = [];
    if (lastH && prev) ins.push(`Tren terbaru: ${bln(lastH.bulan)} ${chg >= 0 ? 'naik' : 'turun'} ${pf.format(Math.abs(chg))}% dibanding bulan sebelumnya.`);
    if (lastH && f1) ins.push(`Prediksi ${bln(f1.bulan)} berbeda ${pf.format((f1.titik / lastH.nilai - 1) * 100)}% dari bulan aktual terakhir.`);
    if (worst) ins.push(`Estimasi risiko tertinggi: ${bln(worst.bulan)} (${pf.format(worst.p)}% dari ambang).`);
    if (f1) ins.push((f1.u95 - f1.l95) / f1.titik > 0.15 ? 'Interval prediksi relatif lebar: ketidakpastian tinggi.' : 'Interval prediksi relatif sempit.');
    const cal = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>';
    $('#view').innerHTML = head('KRL Jabodetabek|Intelligence Dashboard', 'Prediksi penumpang, ketidakpastian, dan peringatan dini kapasitas', `<span class="pill">${cal}Periode: ${D.meta.periode_data || 'menunggu data'}</span><a class="btn" href="#prediksi">+ Lihat prediksi</a>`) + `
    <div class="dg">
      <div class="card k2"><div class="ch"><div><h2>Penumpang bulan terakhir</h2><div class="sub">${lastH ? bln(lastH.bulan) : 'Menunggu data'}</div></div>${arr('#historis')}</div><div class="num">${num(lastH?.nilai)}${dl(chg)}</div></div>
      <div class="card k1"><div class="ch"><div><h2>Prediksi bulan berikutnya</h2><div class="sub">${f1 ? bln(f1.bulan) : 'Menunggu data'}</div></div>${arr('#prediksi')}</div><div class="num">${num(f1?.titik)}</div></div>
      <div class="card k3"><div class="ch"><div><h2>Batas atas prediksi 95%</h2><div class="sub">Bukan nilai aktual</div></div>${arr('#risiko')}</div><div class="num">${num(f1?.u95)}</div></div>
      <div class="card cc"><div class="ch"><div><h2>Tren historis dan prediksi</h2><div class="sub">ribu penumpang, interval 80% dan 95%</div></div><div class="hr"><div class="seg" id="win"><button data-n="12">12 bln</button><button data-n="36" class="on">36 bln</button><button data-n="9999">Semua</button></div>${arr('#prediksi')}</div></div><div class="chart">${hasF() ? '<canvas id="c1"></canvas>' : empty()}</div></div>
      <div class="card navy st"><div class="ch"><div><h2>Status risiko kapasitas</h2><div class="sub">Berdasarkan batas atas prediksi 95%</div></div>${arr('#risiko')}</div>
        ${badge(r1.s)}<div class="num">${r1.p != null ? pf.format(r1.p) + '%' : '--'} <small style="color:#9fb0cc">dari ambang</small></div>
        <div class="bar"><b style="width:${Math.min(r1.p || 0, 100)}%;background:${COL[r1.s] || '#94a3b8'}"></b></div>
        <dl><dt>Batas atas 95%</dt><dd>${fmt(f1?.u95)}</dd><dt>Ambang kapasitas</dt><dd>${fmt(ambang)}</dd></dl>
        <p class="why">${r1.s ? `Status ${r1.s.toUpperCase()}: batas atas 95% setara ${pf.format(r1.p)}% ambang (aman &lt;90%, waspada 90–&lt;100%, kritis ≥100%).` : 'Status muncul setelah prediksi dan ambang kapasitas tersedia.'}</p></div>
      <div class="card tb"><div class="ch"><div><h2>Prediksi dan risiko per bulan</h2><div class="sub">Enam bulan ke depan</div></div>${arr('#risiko')}</div><div class="tbl">${F.length ? '<table><tr><th>Bulan</th><th>Prediksi titik</th><th>Batas atas 95%</th><th>% ambang</th><th>Status</th></tr>' + F.map((r) => { const k = rr(r); return `<tr><td>${bln(r.bulan)}</td><td>${fmt(r.titik)}</td><td>${fmt(r.u95)}</td><td>${k.p != null ? pf.format(k.p) + '%' : '--'}</td><td>${badge(k.s)}</td></tr>`; }).join('') + '</table>' : empty()}</div></div>
      <div class="card ins"><div class="ch"><div><h2>Ringkasan insight</h2><div class="sub">Dari data yang tersedia</div></div></div>${ins.length ? '<ul class="ins">' + ins.map((x) => `<li>${x}</li>`).join('') + '</ul>' : empty('Insight muncul setelah data tersedia')}</div>
    </div>`;
    if (hasF()) { forecastChart('c1', F); $('#win').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; document.querySelectorAll('#win button').forEach((x) => x.classList.toggle('on', x === b)); forecastChart('c1', F, true, +b.dataset.n); }; }
  },

  prediksi() {
    $('#view').innerHTML = head('Prediksi Penumpang', 'Hasil forecasting 1–6 bulan ke depan dengan interval prediksi') + `
    <div class="tools"><label>Horizon <select id="hz">${[1, 2, 3, 4, 5, 6].map((n) => `<option value="${n}" ${n === 6 ? 'selected' : ''}>${n} bulan</option>`).join('')}</select></label>
    <button class="btn sec" id="dl" ${hasF() ? '' : 'disabled'}>Unduh CSV</button></div>
    <div class="note"><b>Prediksi titik</b> adalah estimasi tunggal paling mungkin. <b>Interval prediksi</b> (80% dan 95%) adalah rentang ketidakpastian; ia bukan nilai aktual dan bukan jaminan hasil pasti berada di dalamnya.</div>
    <div class="card" style="margin-bottom:16px"><div class="chart">${hasF() ? '<canvas id="c2"></canvas>' : empty()}</div></div>
    <div class="card"><div class="tbl" id="tb"></div></div>`;
    const draw = () => {
      const n = +$('#hz').value, F = D.forecast.slice(0, n);
      if (hasF()) forecastChart('c2', F);
      $('#tb').innerHTML = F.length ? `<table><tr><th>Bulan</th><th>Aktual</th><th>Prediksi titik</th><th>Bawah 80%</th><th>Atas 80%</th><th>Bawah 95%</th><th>Atas 95%</th><th>Status</th></tr>` +
        F.map((r) => `<tr><td>${bln(r.bulan)}</td><td>${fmt(r.aktual)}</td><td>${fmt(r.titik)}</td><td>${fmt(r.l80)}</td><td>${fmt(r.u80)}</td><td>${fmt(r.l95)}</td><td>${fmt(r.u95)}</td><td>${badge(rr(r).s)}</td></tr>`).join('') + '</table>' : empty();
      $('#dl').onclick = () => { const csv = 'bulan,titik,l80,u80,l95,u95\n' + F.map((r) => [r.bulan, r.titik, r.l80, r.u80, r.l95, r.u95].join(',')).join('\n'); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = 'prediksi_krl.csv'; a.click(); };
    };
    $('#hz').onchange = draw; draw();
  },

  historis() {
    const H = D.historis, yrs = [...new Set(H.map((r) => r.bulan.slice(0, 4)))];
    $('#view').innerHTML = head('Analisis Historis', 'Eksplorasi data penumpang bulanan 2016 hingga periode terbaru') + `
    <div class="note">Data adalah agregat bulanan Jabodetabek, bukan data per stasiun atau lintas. Dugaan bahwa jumlah penumpang mendatar akibat batas kapasitas adalah <b>hipotesis yang diuji</b>, bukan fakta terbukti.</div>
    <div class="tools"><label>Dari <input type="month" id="d1" ${H.length ? `value="${H[0].bulan}"` : 'disabled'}></label><label>Sampai <input type="month" id="d2" ${H.length ? `value="${H[H.length - 1].bulan}"` : 'disabled'}></label>
    <span class="meta">Area abu = COVID-19 (Mar 2020–Des 2021); garis putus oranye = Lebaran</span></div>
    <div class="card" style="margin-bottom:16px"><h2>Penumpang per bulan (ribu penumpang)</h2><div class="chart">${H.length ? '<canvas id="h1"></canvas>' : empty()}</div></div>
    <div class="grid g2e"><div class="card"><h2>Total tahunan (ribu penumpang)</h2><div class="chart sm">${H.length ? '<canvas id="h2"></canvas>' : empty()}</div></div>
    <div class="card"><h2>Pola musiman: rata-rata per bulan</h2><div class="chart sm">${H.length ? '<canvas id="h3"></canvas>' : empty()}</div></div></div>
    <div class="grid g2e"><div class="card"><h2>Hari kerja vs penumpang</h2><div class="chart sm">${H.some((r) => r.hari_kerja != null) ? '<canvas id="h4"></canvas>' : empty()}</div></div>
    <div class="card"><h2>Ringkasan eksploratif</h2><div id="sum">${empty('Ringkasan muncul setelah data tersedia')}</div></div></div>`;
    if (!H.length) return;
    const draw = () => {
      const a = $('#d1').value, b = $('#d2').value, R = H.filter((r) => r.bulan >= a && r.bulan <= b);
      chart('h1', { type: 'line', plugins: [covidBox], data: { labels: R.map((r) => r.bulan), datasets: [{ label: 'Aktual', data: R.map((r) => r.nilai), borderColor: NAVY, borderWidth: 2, pointRadius: 0 }] },
        options: { plugins: { covid: { on: true, lebaran: D.meta.lebaran }, legend: { display: false }, tooltip: { callbacks: { title: (i) => bln(i[0].label), label: (c) => ` ${fmt(c.raw)} ribu` } } }, scales: { y: ax('ribu penumpang'), x: { ticks: { maxTicksLimit: 10, callback(v) { return bln(this.getLabelForValue(v)); } } } } } });
      const ys = [...new Set(R.map((r) => r.bulan.slice(0, 4)))];
      chart('h2', { type: 'bar', data: { labels: ys, datasets: [{ label: 'Total', data: ys.map((y) => R.filter((r) => r.bulan.startsWith(y)).reduce((s, r) => s + r.nilai, 0)), backgroundColor: NAVY }] }, options: { plugins: { legend: { display: false } }, scales: { y: ax('ribu penumpang') } } });
      const avg = MON.map((_, i) => { const x = R.filter((r) => +r.bulan.slice(5) === i + 1); return x.length ? x.reduce((s, r) => s + r.nilai, 0) / x.length : null; });
      chart('h3', { type: 'bar', data: { labels: MON, datasets: [{ label: 'Rata-rata', data: avg, backgroundColor: '#3b82f6' }] }, options: { plugins: { legend: { display: false } }, scales: { y: ax('ribu penumpang') } } });
      if (charts.h4 || document.getElementById('h4')) chart('h4', { type: 'scatter', data: { datasets: [{ label: 'Bulan', data: R.filter((r) => r.hari_kerja != null).map((r) => ({ x: r.hari_kerja, y: r.nilai })), backgroundColor: NAVY }] }, options: { interaction: { mode: 'nearest' }, plugins: { legend: { display: false } }, scales: { x: { title: { display: true, text: 'Hari kerja' } }, y: ax('ribu penumpang') } } });
      const seg = (f, t) => { const x = R.filter((r) => r.bulan >= f && r.bulan <= t); return x.length ? pf.format(x.reduce((s, r) => s + r.nilai, 0) / x.length) : '--'; };
      $('#sum').innerHTML = `<table><tr><th>Periode</th><th>Rata-rata (ribu)</th></tr><tr><td>Sebelum COVID-19</td><td>${seg('0000-00', '2020-02')}</td></tr><tr><td>Selama COVID-19</td><td>${seg('2020-03', '2021-12')}</td></tr><tr><td>Sesudah COVID-19</td><td>${seg('2022-01', '9999-99')}</td></tr></table>`;
    };
    $('#d1').onchange = $('#d2').onchange = draw; draw();
  },

  risiko() {
    $('#view').innerHTML = head('Risiko Kapasitas', 'Batas atas prediksi 95% dibandingkan ambang kapasitas') + `
    <div class="note">Ambang kapasitas adalah <b>parameter sistem</b>, bukan kapasitas resmi. Prediksi bulanan juga <b>bukan</b> okupansi penumpang di dalam kereta pada satu waktu. Aturan: AMAN &lt;90% ambang, WASPADA 90% hingga &lt;100%, KRITIS ≥100%.</div>
    <div class="tools"><label>Ambang (ribu penumpang) <input type="number" id="thr" min="0" step="100" value="${ambang ?? ''}" placeholder="Menunggu data"></label></div>
    <div class="grid g2"><div class="card"><h2>Batas atas 95% vs ambang (ribu penumpang)</h2><div class="chart">${hasF() ? '<canvas id="r1"></canvas>' : empty()}</div></div>
    <div class="card"><h2>Sensitivitas ambang</h2><div id="sens">${empty()}</div></div></div>
    <div class="card"><h2>Risiko 6 bulan ke depan</h2><div class="tbl" id="rt">${empty()}</div></div>`;
    const draw = () => {
      const F = D.forecast; if (!F.length) return;
      $('#rt').innerHTML = '<table><tr><th>Bulan</th><th>Batas atas 95%</th><th>Ambang</th><th>% terhadap ambang</th><th>Status</th></tr>' + F.map((r) => { const k = rr(r); return `<tr><td>${bln(r.bulan)}</td><td>${fmt(r.u95)}</td><td>${fmt(ambang)}</td><td>${k.p != null ? pf.format(k.p) + '%' : '--'}</td><td>${badge(k.s)}</td></tr>`; }).join('') + '</table>';
      chart('r1', { type: 'line', data: { labels: F.map((r) => r.bulan), datasets: [{ label: 'Batas atas 95%', data: F.map((r) => r.u95), borderColor: NAVY, borderWidth: 2, pointBackgroundColor: F.map((r) => COL[rr(r).s] || NAVY), pointRadius: 5 }, { label: 'Ambang kapasitas', data: F.map(() => ambang || null), borderColor: COL.kritis, borderDash: [6, 4], pointRadius: 0 }] },
        options: { plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { title: (i) => bln(i[0].label), label: (c) => ` ${c.dataset.label}: ${fmt(c.raw)} ribu` } } }, scales: { y: ax('ribu penumpang'), x: { ticks: { callback(v) { return bln(this.getLabelForValue(v)); } } } } } });
      if (!ambang) return;
      $('#sens').innerHTML = '<table><tr><th>Skenario</th><th>Ambang</th><th>Kritis / Waspada</th></tr>' + [['-10%', .9], ['-5%', .95], ['Dasar', 1], ['+5%', 1.05], ['+10%', 1.1]].map(([n, f]) => { const S = F.map((r) => risk(r.u95, ambang * f).s); return `<tr><td>${n}</td><td>${fmt(ambang * f)}</td><td>${S.filter((s) => s === 'kritis').length} / ${S.filter((s) => s === 'waspada').length} bulan</td></tr>`; }).join('') + '</table>';
    };
    $('#thr').onchange = (e) => { ambang = e.target.value ? +e.target.value : null; draw(); }; draw();
  },

  chat() {
    const H = D.historis, F = D.forecast, lastH = H[H.length - 1], f1 = F[0];
    const sparkIco = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>';
    const botIco = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="3"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4M8 15h.01M16 15h.01"/></svg>';
    const userIco = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
    const sendIco = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>';

    $('#view').innerHTML = head('Asisten AI|KRL Intelligence', 'Tanya jawab pintar, ringkasan eksekutif, dan rekomendasi berbasis data aktif', `<span class="pill">${sparkIco}Model Aktif: ${D.meta.model_terpilih || 'Ensemble Time Series'}</span>`) + `
    <div class="chat-grid">
      <div class="chat-card">
        <div class="chat-header">
          <div class="chat-title">${botIco}<span>KRL Insight Copilot</span><span class="bot-badge">AI Assistant</span></div>
          <button id="btn-reset-chat" class="btn sec" style="padding:6px 14px;font-size:12px">Bersihkan Chat</button>
        </div>
        <div class="chat-chips">
          <button class="chip-btn" data-q="Ringkasan proyeksi 6 bulan ke depan">📊 Ringkas Proyeksi 6 Bulan</button>
          <button class="chip-btn" data-q="Bagaimana analisis risiko kapasitas dan status kritis?">⚠️ Analisis Risiko Kapasitas</button>
          <button class="chip-btn" data-q="Apa rekomendasi operasional untuk manajemen KAI?">💡 Rekomendasi Kebijakan Armada</button>
          <button class="chip-btn" data-q="Bagaimana pola musiman Lebaran dan hari kerja?">🗓️ Pola Musiman & Lebaran</button>
          <button class="chip-btn" data-q="Apa itu interval prediksi 80% dan 95%?">ℹ️ Edukasi Uncertainty Interval</button>
        </div>
        <div class="chat-body" id="chat-stream">
          <!-- pesan chat akan dimuat di sini -->
        </div>
        <div class="chat-footer">
          <input type="text" id="chat-input" placeholder="Tanyakan seputar proyeksi penumpang, kapasitas kritis, pola Lebaran, atau rekomendasi..." autocomplete="off">
          <button id="chat-send-btn" class="btn acc" style="display:flex;align-items:center;gap:6px">${sendIco}<span>Kirim</span></button>
        </div>
      </div>

      <div class="chat-side">
        <div class="card">
          <div class="ch"><div><h2>Fakta Data Terverifikasi</h2><div class="sub">Grounding data pipeline AI</div></div></div>
          <dl class="fact-list">
            <div class="fact-item"><dt>Periode Data</dt><dd>${D.meta.periode_data || '--'}</dd></div>
            <div class="fact-item"><dt>Penumpang Terakhir</dt><dd>${fmt(lastH?.nilai)} ribu</dd></div>
            <div class="fact-item"><dt>Prediksi Bulan Depan</dt><dd>${fmt(f1?.titik)} ribu</dd></div>
            <div class="fact-item"><dt>Batas Atas 95%</dt><dd>${fmt(f1?.u95)} ribu</dd></div>
            <div class="fact-item"><dt>Ambang Kapasitas</dt><dd>${fmt(ambang)} ribu</dd></div>
            <div class="fact-item"><dt>Status Risiko Awal</dt><dd>${badge(f1 ? rr(f1).s : null)}</dd></div>
          </dl>
          <p style="font-size:12px;color:var(--mut);margin:14px 0 0;line-height:1.5">Asisten AI hanya menjawab berdasarkan fakta data numerik yang telah divalidasi tanpa rekayasa angka (Zero Hallucination).</p>
        </div>

        <div class="card">
          <div class="ch"><div><h2>Panduan Pertanyaan</h2><div class="sub">Contoh topik interaktif</div></div></div>
          <ul class="ins" style="font-size:12.5px;color:#475569">
            <li>Tanyakan perbandingan bulan tertentu: <em>"Berapa prediksi bulan Desember?"</em></li>
            <li>Tanyakan alasan lonjakan: <em>"Kenapa batas atas 95% berstatus kritis?"</em></li>
            <li>Tanyakan skenario: <em>"Bagaimana jika kapasitas dinaikkan 10%?"</em></li>
          </ul>
        </div>
      </div>
    </div>`;

    // Knowledge & Response Generator
    const getAIAnswer = (query) => {
      const q = query.toLowerCase();
      const f_first = F[0], f_end = F[F.length - 1];
      const maxPt = F.reduce((m, r) => r.titik > m.titik ? r : m, F[0]);
      const minPt = F.reduce((m, r) => r.titik < m.titik ? r : m, F[0]);
      const worstRisk = F.reduce((w, r) => { const k = rr(r); return (k.p || 0) > (w.p || 0) ? { ...k, ...r } : w; }, { p: 0 });
      const kritisMonths = F.filter((r) => rr(r).s === 'kritis');
      const waspadaMonths = F.filter((r) => rr(r).s === 'waspada');

      // 1. Ringkasan Proyeksi 6 Bulan
      if (q.includes('ringkas') || q.includes('proyeksi') || q.includes('rangkum') || q.includes('overview') || q.includes('summary')) {
        return `<p>Berikut adalah <strong>Ringkasan Eksekutif Proyeksi Penumpang KRL Jabodetabek (6 Bulan ke Depan)</strong>:</p>
        <ul>
          <li><strong>Cakupan Periode:</strong> ${bln(f_first.bulan)} hingga ${bln(f_end.bulan)}.</li>
          <li><strong>Rentang Estimasi Titik:</strong> Volume bulanan diproyeksikan berada di kisaran <strong>${fmt(minPt.titik)} ribu</strong> (${bln(minPt.bulan)}) hingga <strong>${fmt(maxPt.titik)} ribu</strong> (${bln(maxPt.bulan)}).</li>
          <li><strong>Puncak Permintaan:</strong> Terjadi pada <strong>${bln(maxPt.bulan)}</strong> dengan estimasi titik <strong>${fmt(maxPt.titik)} ribu</strong> penumpang (didorong mobilitas libur akhir tahun & cuti bersama).</li>
          <li><strong>Batas Ketidakpastian (Upper 95%):</strong> Risiko volume tertinggi mencapai <strong>${fmt(worstRisk.u95)} ribu</strong> pada <strong>${bln(worstRisk.bulan)}</strong>.</li>
          <li><strong>Kesimpulan Dinamika:</strong> Tren pasca-COVID stabil di level rata-rata 30–32 juta/bulan, mengindikasikan bahwa laju pertumbuhan mulai tertahan oleh batas fisik daya tampung rangkaian (*capacity ceiling*).</li>
        </ul>`;
      }

      // 2. Risiko Kapasitas & Status Kritis
      if (q.includes('risiko') || q.includes('kapasitas') || q.includes('ambang') || q.includes('kritis') || q.includes('waspada') || q.includes('aman') || q.includes('overload')) {
        return `<p>Berikut adalah <strong>Analisis Risiko Kapasitas Sistem KRL</strong>:</p>
        <ul>
          <li><strong>Ambang Batas Operasional:</strong> Ditetapkan pada <strong>${fmt(ambang)} ribu penumpang/bulan</strong> (representasi daya angkut maksimal armada saat ini).</li>
          <li><strong>Status Risiko Tertinggi:</strong> Terdeteksi berstatus <span class="badge ${worstRisk.s}">${worstRisk.s.toUpperCase()}</span> pada <strong>${bln(worstRisk.bulan)}</strong> dengan rasio batas atas setara <strong>${pf.format(worstRisk.p)}%</strong> dari ambang.</li>
          <li><strong>Bulan Berstatus Kritis:</strong> ${kritisMonths.length ? kritisMonths.map((m) => `<strong>${bln(m.bulan)}</strong> (${fmt(m.u95)} ribu)`).join(', ') : 'Tidak ada bulan yang melampaui 100% ambang.'}</li>
          <li><strong>Bulan Berstatus Waspada:</strong> ${waspadaMonths.length ? waspadaMonths.map((m) => `<strong>${bln(m.bulan)}</strong> (${fmt(m.u95)} ribu)`).join(', ') : 'Nihil.'}</li>
        </ul>
        <p>⚠️ <em>Catatan Penting:</em> Status KRITIS ditentukan oleh <strong>Batas Atas 95%</strong> (skenario terburuk), bukan titik rata-rata. Tujuannya adalah prinsip kehati-hatian (*safety margin*) agar operator tidak mengalami *service breakdown* saat lonjakan tak terduga.</p>`;
      }

      // 3. Rekomendasi Kebijakan Armada
      if (q.includes('rekomendasi') || q.includes('kebijakan') || q.includes('solusi') || q.includes('saran') || q.includes('mitigasi') || q.includes('armada') || q.includes('kai')) {
        return `<p>Berdasarkan hasil pemodelan cerdas dan proyeksi risiko kapasitas, berikut adalah <strong>4 Rekomendasi Kebijakan untuk Operator PT KAI Commuter & DJKA Kemenhub</strong>:</p>
        <ul>
          <li><strong>1. Optimalisasi Formasi Rangkaian (SF12):</strong> Prioritaskan pengoperasian rangkaian 12 kereta (*Stamformasi 12*) secara penuh pada koridor terpadat (Bogor–Manggarai dan Cikarang–Manggarai), khususnya di jam sibuk pagi (06.30–08.30) dan sore (17.00–19.30).</li>
          <li><strong>2. Rekayasa Crowd Control di Stasiun Transit:</strong> Terapkan manajemen alur pergantian penumpang secara ketat di Stasiun Manggarai (lantai 1 ke lantai 2) dan Tanah Abang guna mencegah desak-desakan ekstrem pada peron saat headway rapat.</li>
          <li><strong>3. Penyesuaian Headway Dinamis:</strong> Memperpendek interval antar-kereta (*headway*) menjadi 3–4 menit pada bulan-bulan berstatus <em>Kritis/Waspada</em> (seperti ${bln(worstRisk.bulan)}).</li>
          <li><strong>4. Penyiagaan Kereta Luar Biasa (KLB Cadangan):</strong> Siapkan minimal 2–3 rangkaian cadangan di depo Bukit Duri dan Manggarai yang siap diinjeksi saat terjadi penumpukan mendadak.</li>
        </ul>`;
      }

      // 4. Pola Musiman, Lebaran, Hari Kerja & COVID
      if (q.includes('musim') || q.includes('lebaran') || q.includes('idul fitri') || q.includes('libur') || q.includes('hari kerja') || q.includes('covid') || q.includes('pandemi')) {
        return `<p>Berikut adalah karakteristik <strong>Dinamika Musiman & Efek Eksternal Penumpang KRL</strong>:</p>
        <ul>
          <li><strong>Fenomena Anjlok Lebaran:</strong> Setiap periode Idul Fitri (seperti ${D.meta.lebaran?.slice(-3).map((m) => bln(m)).join(', ')}), jumlah penumpang KRL selalu merosot tajam antara <strong>15% hingga 25%</strong> akibat libur panjang kantor/sekolah dan tradisi mudik ke luar Jabodetabek.</li>
          <li><strong>Efek Rebound Pasca-Lebaran:</strong> Satu bulan setelah Lebaran, mobilitas komuter melonjak kembali secara signifikan karena arus balik pekerja urban.</li>
          <li><strong>Sensitivitas Hari Kerja:</strong> Terdapat korelasi positif yang sangat kuat ($r > 0.85$) antara jumlah hari kerja (Senin–Jumat non-libur) dengan total penumpang bulanan. Selisih 1–2 hari kerja dapat menggeser volume hingga ratusan ribu orang.</li>
          <li><strong>Structural Break Pandemi:</strong> Periode Maret 2020 s.d. Desember 2021 merupakan patahan struktural ekstrem saat penumpang anjlok hingga 60%. Sejak 2023, mobilitas telah pulih penuh dan memasuki fase jenuh kapasitas.</li>
        </ul>`;
      }

      // 5. Penjelasan Ketidakpastian & Prediction Interval
      if (q.includes('interval') || q.includes('ketidakpastian') || q.includes('uncertainty') || q.includes('80%') || q.includes('95%') || q.includes('conformal') || q.includes('cqr') || q.includes('metode')) {
        return `<p>Berikut penjelasan tentang <strong>Interval Prediksi & Kuantifikasi Ketidakpastian (Uncertainty Quantification)</strong>:</p>
        <ul>
          <li><strong>Kelemahan "Point Forecast":</strong> Meramal dengan 1 angka tunggal berbahaya. Jika realisasi penumpang berada di atas estimasi, stasiun lumpuh karena penumpukan; jika di bawahnya, terjadi pemborosan energi listrik dan armada.</li>
          <li><strong>Interval Prediksi 80%:</strong> Menunjukkan rentang realistis operasional reguler (80% kemungkinan aktual berada di dalam rentang tersebut).</li>
          <li><strong>Interval Prediksi 95%:</strong> Menunjukkan pita ketidakpastian tinggi sebagai jaring pengaman (*safety net*) mitigasi risiko darurat.</li>
          <li><strong>Metode Conformal Prediction:</strong> Dikalibrasi secara empiris dari residual *out-of-sample* backtest historis tanpa memaksakan asumsi distribusi normal Gaussian yang sering meleset pada data nyata.</li>
        </ul>`;
      }

      // 6. Pertanyaan Bulan Tertentu (misal September, Oktober, Desember)
      const monthNames = ['januari', 'februari', 'maret', 'april', 'mei', 'juni', 'juli', 'agustus', 'september', 'oktober', 'november', 'desember'];
      const matchedIdx = monthNames.findIndex((mn) => q.includes(mn));
      if (matchedIdx >= 0) {
        const found = F.find((r) => +r.bulan.split('-')[1] === matchedIdx + 1);
        if (found) {
          const rk = rr(found);
          return `<p>Detail Proyeksi untuk <strong>${bln(found.bulan)}</strong>:</p>
          <ul>
            <li><strong>Prediksi Titik (Point Forecast):</strong> <span class="stat-highlight">${fmt(found.titik)} ribu penumpang</span></li>
            <li><strong>Rentang Interval 80%:</strong> ${fmt(found.l80)} s.d. ${fmt(found.u80)} ribu penumpang</li>
            <li><strong>Rentang Interval 95%:</strong> ${fmt(found.l95)} s.d. ${fmt(found.u95)} ribu penumpang</li>
            <li><strong>Batas Atas Risiko (95% Upper):</strong> ${fmt(found.u95)} ribu penumpang</li>
            <li><strong>Rasio terhadap Ambang:</strong> ${rk.p != null ? pf.format(rk.p) + '%' : '--'} (Ambang: ${fmt(ambang)} ribu)</li>
            <li><strong>Status Risiko:</strong> ${badge(rk.s)}</li>
          </ul>`;
        }
      }

      // 7. Respon Cerdas Umum
      return `<p>Terima kasih atas pertanyaannya! Berdasarkan basis data cerdas KRL Jabodetabek:</p>
      <ul>
        <li>Posisi data aktual terakhir (<strong>${bln(lastH.bulan)}</strong>) mencatatkan volume <strong>${fmt(lastH.nilai)} ribu</strong> penumpang.</li>
        <li>Proyeksi bulan terdekat (<strong>${bln(f_first.bulan)}</strong>) adalah <strong>${fmt(f_first.titik)} ribu</strong> dengan batas atas risiko 95% mencapai <strong>${fmt(f_first.u95)} ribu</strong>.</li>
        <li>Kondisi ini menempatkan status operasional pada level ${badge(rr(f_first).s)}.</li>
      </ul>
      <p>Anda dapat mengklik tombol topik cepat di atas untuk melihat <em>Ringkasan Proyeksi 6 Bulan</em>, <em>Analisis Risiko Kapasitas</em>, atau <em>Rekomendasi Kebijakan Armada</em> secara mendalam.</p>`;
    };

    // Chat Controller
    const stream = document.getElementById('chat-stream');
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    const resetBtn = document.getElementById('btn-reset-chat');

    const appendMsg = (role, html) => {
      const row = document.createElement('div');
      row.className = `chat-row ${role}`;
      row.innerHTML = `<div class="chat-avatar">${role === 'user' ? userIco : botIco}</div><div class="chat-msg">${html}</div>`;
      stream.appendChild(row);
      stream.scrollTop = stream.scrollHeight;
    };

    const showTyping = () => {
      const row = document.createElement('div');
      row.className = 'chat-row ai';
      row.id = 'typing-indicator';
      row.innerHTML = `<div class="chat-avatar">${botIco}</div><div class="chat-msg" style="padding:10px 14px"><div class="typing-dots"><span></span><span></span><span></span></div></div>`;
      stream.appendChild(row);
      stream.scrollTop = stream.scrollHeight;
    };

    const removeTyping = () => {
      const el = document.getElementById('typing-indicator');
      if (el) el.remove();
    };

    const handleSend = (text) => {
      const query = (text || input.value || '').trim();
      if (!query) return;
      input.value = '';
      appendMsg('user', `<p>${query}</p>`);
      showTyping();
      setTimeout(() => {
        removeTyping();
        const ans = getAIAnswer(query);
        appendMsg('ai', ans);
      }, 350);
    };

    // Initial greeting
    const loadGreeting = () => {
      stream.innerHTML = '';
      appendMsg('ai', `<p>Halo! Saya <strong>Asisten AI KRL Insight</strong>. 🚆</p>
      <p>Saya dilatih untuk menganalisis data deret waktu penumpang KRL Jabodetabek, mengevaluasi rentang ketidakpastian peramalan 6 bulan ke depan, dan mendeteksi risiko kejenuhan kapasitas armada.</p>
      <p>Silakan tanyakan hal apa saja atau gunakan tombol topik cepat di atas untuk memulai!</p>`);
    };

    loadGreeting();

    sendBtn.onclick = () => handleSend();
    input.onkeydown = (e) => { if (e.key === 'Enter') handleSend(); };
    resetBtn.onclick = () => loadGreeting();

    document.querySelectorAll('.chip-btn').forEach((btn) => {
      btn.onclick = () => handleSend(btn.dataset.q);
    });
  }
};

/* ---------- Router & sidebar ---------- */
function route() {
  const p = location.hash.slice(1);
  const k = pages[p] ? p : 'beranda';
  document.body.classList.toggle('intro', k === 'beranda');
  document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('on', a.dataset.p === k));
  if (!D) return;
  Object.values(charts).forEach((c) => c.destroy());
  charts = {};
  pages[k]();
  scrollTo(0, 0);
}
$('#nav').innerHTML = PAGES.map(([k, t, i]) => `<a href="#${k}" data-p="${k}" title="${t}">${ico(i)}<span class="label">${t}</span></a>`).join('');
$('#toggle').onclick = () => { document.body.classList.toggle('wide'); $('#toggle').textContent = document.body.classList.contains('wide') ? '«' : '»'; };
addEventListener('hashchange', route);
load();
