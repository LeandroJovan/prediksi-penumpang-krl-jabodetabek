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
  ['evaluasi', 'Evaluasi Model', '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'],
  ['tentang', 'Tentang Sistem', '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>']
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
    const ready = D.historis.length && D.forecast.length, demo = DEMO_FLAG();
    const st = demo ? 'Mode demo' : ready ? 'Data terhubung' : 'Menunggu data';
    const I = (d, n = 22) => `<svg viewBox="0 0 24 24" width="${n}" height="${n}" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
    const logo = '<svg viewBox="0 0 32 32" width="32" height="32"><rect x="6" y="3" width="20" height="21" rx="5" fill="#0b1f3f"/><rect x="9" y="7" width="14" height="8" rx="2" fill="#fff"/><circle cx="11.5" cy="19.5" r="1.7" fill="#fff"/><circle cx="20.5" cy="19.5" r="1.7" fill="#fff"/><path d="M9 29l3-5m11 5l-3-5" stroke="#0b1f3f" stroke-width="2" stroke-linecap="round"/></svg>';
    const P = { chart: '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>', band: '<path d="M3 8c6-4 12 4 18 0M3 16c6-4 12 4 18 0"/>', warn: '<path d="M12 3l10 18H2z"/><path d="M12 10v5"/>', bars: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>', cal: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>', dl: '<path d="M12 4v11m-4-4l4 4 4-4M5 20h14"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>', lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>', check: '<path d="M5 12l4 4 10-10"/>', db: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/>', target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>' };
    const small = [['#historis', P.cal, 'Analisis Historis', 'Tren, musiman, COVID-19, dan Lebaran.'], ['#risiko', P.warn, 'Risiko Kapasitas', 'Status per bulan dan sensitivitas ambang.'], ['#evaluasi', P.bars, 'Evaluasi Model', 'Lima model, metrik backtesting.'], ['#prediksi', P.dl, 'Ekspor Hasil', 'Unduh tabel prediksi sebagai CSV.'], ['#tentang', P.info, 'Tentang Sistem', 'Metode, keterbatasan, dan alur kerja.']];
    const why = [[P.band, 'Interval prediksi', 'Rentang 80% dan 95% menyertai setiap prediksi titik.'], [P.target, 'Conformal prediction', 'Interval dibentuk dari galat backtesting yang nyata.'], [P.bars, 'Backtesting', 'Lima model diuji, hasilnya ditampilkan apa adanya.'], [P.warn, 'Status risiko', 'Aman, Waspada, Kritis dengan aturan yang tetap.'], [P.lock, 'Tanpa data leakage', 'Pelatihan tidak melihat data masa depan.'], [P.db, 'Data transparan', 'Tanpa data tersedia, tertulis “Menunggu data”.']];
    const flow = [['Data BPS', 'Agregat bulanan Jabodetabek'], ['Data Preparation', 'Pembersihan dan penyelarasan bulan'], ['Feature Engineering', 'Kalender, hari kerja, Lebaran'], ['Forecasting', 'Lima model dibandingkan'], ['Prediction Interval', 'Conformal prediction 80% dan 95%'], ['Risk Assessment', 'Batas atas 95% vs ambang'], ['Dashboard', 'Tampilan untuk pengambil keputusan']];
    const thumb = (ban) => `<svg viewBox="0 0 300 120" preserveAspectRatio="xMidYMid slice"><rect width="300" height="120" fill="#eaf1fb"/>${ban ? '<path d="M170 70L290 25V95Z" fill="#12305c" opacity=".14"/><path d="M170 70L290 42V78Z" fill="#12305c" opacity=".25"/>' : ''}<path d="M10 95C40 60 70 90 100 62S150 55 170 70" fill="none" stroke="#12305c" stroke-width="3"/><path d="${ban ? 'M170 70C210 62 250 56 290 52' : 'M170 70L290 40'}" stroke="#2563eb" stroke-width="3" stroke-dasharray="6 4" fill="none"/></svg>`;
    $('#view').innerHTML = `<div class="lp">
    <header class="lp-top wrap"><a class="lp-brand" href="#beranda">${logo}KRL Insight</a>
      <nav class="lp-links"><a href="#fitur">Fitur</a><a href="#kenapa">Keunggulan</a><a href="#cara">Cara kerja</a><a href="#tentang">Tentang</a></nav>
      <a class="btn acc" href="#dashboard">Buka dashboard</a></header>

    <section class="lp-hero"><div class="wrap lp-hg">
      <div class="lp-copy"><span class="lp-eyebrow">Prediksi &amp; peringatan dini kapasitas</span>
        <h1>Prediksi Penumpang <em>KRL Jabodetabek</em> yang Lebih Siap</h1>
        <p>Perkirakan jumlah penumpang 1–6 bulan ke depan, lihat seberapa pasti perkiraannya, dan terima peringatan dini sebelum kapasitas terlampaui.</p>
        <div class="hero-cta"><a class="btn acc lg" href="#dashboard">Masuk ke dashboard</a><a class="btn sec lg" href="#cara">Lihat cara kerja</a></div>
        <ul class="lp-marks"><li>${I(P.check, 18)}Data BPS</li><li>${I(P.check, 18)}Interval 80% &amp; 95%</li><li>${I(P.check, 18)}Evaluasi transparan</li></ul></div>
      <div class="lp-scene"><svg viewBox="0 0 640 430" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Ilustrasi KRL di stasiun">
        <rect width="640" height="430" fill="#cfe3fb"/><circle cx="520" cy="90" r="46" fill="#fff" opacity=".75"/>
        <g fill="#a9c8ee">${[[20, 150, 70, 170], [100, 110, 60, 210], [170, 170, 80, 150], [330, 130, 70, 190], [410, 175, 60, 145], [480, 120, 80, 200], [570, 160, 70, 160]].map(([x, y, w, h]) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"/>`).join('')}</g>
        <rect y="318" width="640" height="112" fill="#e8eef7"/><rect y="318" width="640" height="10" fill="#94a3b8"/>
        <rect x="-10" y="226" width="680" height="94" rx="30" fill="#fff"/><rect x="-10" y="268" width="680" height="16" fill="#12305c"/><rect x="-10" y="284" width="680" height="6" fill="#2563eb"/>
        ${[10, 120, 230, 340, 450].map((x) => `<rect x="${x}" y="244" width="84" height="38" rx="9" fill="#12305c" opacity=".88"/>`).join('')}
        <rect x="560" y="240" width="60" height="50" rx="12" fill="#12305c"/>
        ${[70, 280, 490].map((x) => `<circle cx="${x}" cy="326" r="14" fill="#0b1f3f"/>`).join('')}
        <path d="M0 372H640M0 396H640" stroke="#cbd5e1" stroke-width="6"/><path d="M0 40H640" stroke="#64748b" stroke-width="2"/></svg>
        <div class="lp-float"><b>5 model</b><span>dibandingkan lewat backtesting</span></div></div>
    </div></section>

    <section id="fitur" class="lp-sec wrap"><span class="lp-eyebrow">Fitur</span><h2>Cara membaca prediksi sesuai kebutuhan Anda</h2><p class="lp-sub">Mulai dari ringkasan cepat sampai tabel prediksi per bulan. Status data saat ini: ${st}.</p>
      <div class="lp-two">${[['#dashboard', 'Dashboard', 'Penumpang terakhir, prediksi bulan depan, batas atas 95%, dan status risiko dalam satu layar.', 0], ['#prediksi', 'Prediksi Penumpang', 'Pilih horizon 1 sampai 6 bulan, lihat interval 80% dan 95%, serta tabel hasilnya.', 1]].map(([h, t, x, b]) => `<a class="lp-big" href="${h}"><div class="img">${thumb(b)}</div><div class="bd"><h3>${t}</h3><p>${x}</p><span>Buka halaman &rarr;</span></div></a>`).join('')}</div>
      <div class="lp-five">${small.map(([h, d, t, x]) => `<a href="${h}"><span class="ic">${I(d)}</span><h3>${t}</h3><p>${x}</p></a>`).join('')}</div></section>

    <section class="lp-stats"><div class="wrap">${[[P.chart, '1–6 bulan', 'horizon prediksi'], [P.band, '80% &amp; 95%', 'interval prediksi'], [P.bars, '5 model', 'dibandingkan'], [P.db, '7 tahap', 'dari data ke dashboard']].map(([d, n, t]) => `<div>${I(d, 30)}<b>${n}</b><span>${t}</span></div>`).join('')}</div></section>

    <section id="kenapa" class="lp-sec wrap lp-why"><div><span class="lp-eyebrow">Mengapa KRL Insight</span><h2>Lebih dari Sekadar Angka Prediksi</h2>
      <p class="lp-sub">Satu angka bisa menyesatkan. Kami selalu menampilkan ketidakpastian dan mengubahnya menjadi status risiko yang mudah dipahami.</p><a class="btn acc lg" href="#tentang">Pelajari sistem</a></div>
      <div class="lp-six">${why.map(([d, t, x]) => `<div><span class="ic">${I(d)}</span><h3>${t}</h3><p>${x}</p></div>`).join('')}</div></section>

    <section id="cara" class="lp-flow"><div class="wrap lp-fg"><div><span class="lp-eyebrow lt">Cara kerja</span><h2>Dari Data Mentah ke Peringatan Dini</h2><p>Tujuh tahap berurutan. Hasil evaluasi dan angka prediksi hanya muncul bila pipeline sudah mengisinya, tanpa angka karangan.</p><a class="btn light lg" href="#dashboard">Masuk ke dashboard</a></div>
      <ol>${flow.map(([t, x], i) => `<li><b>${i + 1}</b><div><h3>${t}</h3><span>${x}</span></div></li>`).join('')}</ol></div></section>
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
      <div class="card navy st"><div class="ch"><div><h2>Status risiko kapasitas</h2><div class="sub">Berdasarkan batas atas prediksi 95%</div></div>${arr('#risiko')}</div>
        ${badge(r1.s)}<div class="num">${r1.p != null ? pf.format(r1.p) + '%' : '--'} <small style="color:#9fb0cc">dari ambang</small></div>
        <div class="bar"><b style="width:${Math.min(r1.p || 0, 100)}%;background:${COL[r1.s] || '#94a3b8'}"></b></div>
        <dl><dt>Batas atas 95%</dt><dd>${fmt(f1?.u95)}</dd><dt>Ambang kapasitas</dt><dd>${fmt(ambang)}</dd></dl>
        <p class="why">${r1.s ? `Status ${r1.s.toUpperCase()}: batas atas 95% setara ${pf.format(r1.p)}% ambang (aman &lt;90%, waspada 90–&lt;100%, kritis ≥100%).` : 'Status muncul setelah prediksi dan ambang kapasitas tersedia.'}</p></div>
      <div class="card cc"><div class="ch"><div><h2>Tren historis dan prediksi</h2><div class="sub">ribu penumpang, interval 80% dan 95%</div></div><div class="hr"><div class="seg" id="win"><button data-n="12">12 bln</button><button data-n="36" class="on">36 bln</button><button data-n="9999">Semua</button></div>${arr('#prediksi')}</div></div><div class="chart">${hasF() ? '<canvas id="c1"></canvas>' : empty()}</div></div>
      <div class="card k1"><div class="ch"><div><h2>Prediksi bulan berikutnya</h2><div class="sub">${f1 ? bln(f1.bulan) : 'Menunggu data'}</div></div>${arr('#prediksi')}</div><div class="num">${num(f1?.titik)}</div></div>
      <div class="card k2"><div class="ch"><div><h2>Penumpang bulan terakhir</h2><div class="sub">${lastH ? bln(lastH.bulan) : 'Menunggu data'}</div></div>${arr('#historis')}</div><div class="num">${num(lastH?.nilai)}${dl(chg)}</div></div>
      <div class="card k3"><div class="ch"><div><h2>Batas atas prediksi 95%</h2><div class="sub">Bukan nilai aktual</div></div>${arr('#risiko')}</div><div class="num">${num(f1?.u95)}</div></div>
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

  evaluasi() {
    const E = D.evaluasi.keseluruhan, P = D.evaluasi.pasca_covid, ok = E.some((r) => r.mase != null), f = (v, d = 2) => (v == null ? '--' : v.toLocaleString('id-ID', { maximumFractionDigits: d }));
    $('#view').innerHTML = head('Evaluasi Model', 'Performa model berdasarkan backtesting (tanpa data leakage)') + `
    <div class="note">Target coverage: PICP 80% mendekati <b>0,80</b> dan PICP 95% mendekati <b>0,95</b>. MASE &lt; 1 berarti model lebih baik dari naive in-sample. ${ok ? '' : '<b>Hasil backtesting belum tersedia</b>; angka ditampilkan setelah pipeline mengisi data.json.'}</div>
    <div class="card" style="margin-bottom:16px"><div class="tbl"><table><tr><th>Model</th><th>MASE</th><th>RMSE</th><th>MAE</th><th>PICP 80%</th><th>PICP 95%</th><th>MPIW</th><th>Winkler</th><th>MASE &lt; 1</th></tr>
    ${E.map((r) => `<tr><td>${r.model}</td><td>${f(r.mase)}</td><td>${f(r.rmse, 0)}</td><td>${f(r.mae, 0)}</td><td>${f(r.picp80)}</td><td>${f(r.picp95)}</td><td>${f(r.mpiw, 0)}</td><td>${f(r.winkler, 0)}</td><td>${r.mase == null ? '--' : r.mase < 1 ? 'Ya' : 'Tidak'}</td></tr>`).join('')}</table></div></div>
    <div class="grid g2e"><div class="card"><h2>MASE: seluruh periode vs pasca-COVID</h2><div class="chart sm">${ok ? '<canvas id="e1"></canvas>' : empty()}</div></div>
    <div class="card"><h2>Model terpilih</h2><p>${D.meta.model_terpilih ? `<b>${D.meta.model_terpilih}</b> dipilih berdasarkan hasil backtesting.` : 'Belum ada model terpilih. Pemilihan menunggu hasil backtesting aktual.'}</p></div></div>`;
    if (ok) chart('e1', { type: 'bar', data: { labels: E.map((r) => r.model), datasets: [{ label: 'Seluruh periode', data: E.map((r) => r.mase), backgroundColor: NAVY }, { label: 'Pasca-COVID', data: P.map((r) => r.mase), backgroundColor: '#60a5fa' }] }, options: { plugins: { legend: { position: 'bottom' } }, scales: { y: { title: { display: true, text: 'MASE (tanpa satuan)' } } } } });
  },

  tentang() {
    const T = [['Data BPS', 'Data Prep', 'Feature Engineering', 'Forecasting', 'Prediction Interval', 'Risk Assessment', 'Dashboard']];
    $('#view').innerHTML = head('Tentang Sistem', 'Penjelasan singkat sistem KRL Insight') + `<div class="card prose" style="margin-bottom:16px">
    <h2>Latar belakang dan tujuan</h2><p>KRL Jabodetabek melayani jutaan perjalanan setiap bulan. Proyek ini memprediksi jumlah penumpang 1–6 bulan ke depan, menunjukkan ketidakpastiannya, dan memberi peringatan dini jika berisiko melampaui ambang kapasitas.</p>
    <h2>Data dan metode</h2><p>Data berasal dari BPS berupa agregat bulanan Jabodetabek. Model yang dibandingkan: Naive, Seasonal Naive, ETS (Holt-Winters), SARIMAX, dan LightGBM, dievaluasi dengan backtesting tanpa data leakage.</p>
    <h2>Conformal prediction</h2><p>Interval 80% dan 95% dibuat dari galat prediksi historis hasil backtesting, sehingga rentang ketidakpastian mengikuti performa model yang sebenarnya, tanpa asumsi distribusi tertentu.</p>
    <h2>Status risiko</h2><p>Aman jika batas atas 95% di bawah 90% ambang; Waspada pada 90% hingga di bawah 100%; Kritis jika sama dengan atau di atas ambang. Ambang adalah parameter sistem, bukan kapasitas resmi.</p>
    <h2>Keterbatasan</h2><p>Data bulanan tidak menggambarkan okupansi per kereta atau per stasiun. Prediksi dapat meleset saat terjadi kejadian luar biasa. Aplikasi ini adalah sistem pendukung keputusan, bukan pengganti keputusan operasional resmi.</p></div>
    <div class="card"><h2>Alur kerja</h2><div class="flow">${T[0].map((t) => `<span>${t}</span>`).join('<i>&rarr;</i>')}</div></div>`;
  }
};

/* ---------- Router & sidebar ---------- */
function route() {
  const p = location.hash.slice(1); if (['fitur', 'cara', 'prinsip'].includes(p)) { document.getElementById(p)?.scrollIntoView({ behavior: 'smooth' }); return; } const k = pages[p] ? p : 'beranda'; document.body.classList.toggle('intro', k === 'beranda');
  document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('on', a.dataset.p === k));
  if (!D) return; Object.values(charts).forEach((c) => c.destroy()); charts = {}; pages[k](); scrollTo(0, 0);
}
$('#nav').innerHTML = PAGES.map(([k, t, i]) => `<a href="#${k}" data-p="${k}" title="${t}">${ico(i)}<span class="label">${t}</span></a>`).join('');
$('#toggle').onclick = () => { document.body.classList.toggle('wide'); $('#toggle').textContent = document.body.classList.contains('wide') ? '«' : '»'; };
addEventListener('hashchange', route);
load();
