const test = require("node:test");
const assert = require("node:assert/strict");
const { buildInsight } = require("./insight.js");
const chat = require("./chat.js");

const DATA = {
  ambang_kapasitas: { nilai: 34000 },
  forecast: [
    { bulan: "2026-09", titik: 31000, l80: 30000, u80: 32000, l95: 29000, u95: 33400 },
    { bulan: "2026-12", titik: 34400, l80: 33700, u80: 36600, l95: 32400, u95: 37900 },
  ],
};

function fakeFetch(status, body, { throws } = {}) {
  return async () => {
    if (throws) throw new Error("jaringan putus");
    return { ok: status >= 200 && status < 300, status, json: async () => body };
  };
}

test("escapeHtml menetralkan markup dan atribut", () => {
  assert.equal(chat.escapeHtml(`<img src=x onerror="alert(1)">'`), "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&#39;");
  assert.equal(chat.escapeHtml(null), "");
  assert.equal(chat.escapeHtml(42), "42");
});

test("renderAnswer meng-escape semua teks dari server", () => {
  const html = chat.renderAnswer({
    answer: "<script>alert(1)</script>",
    bullets: ['<b onclick="x()">tebal</b>'],
    status: "kritis",
    source: "rules",
    suggestions: ['"><img src=x onerror=alert(1)>'],
  });
  assert.ok(!/<script|<img|<b /i.test(html));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(html.includes('data-q="&quot;&gt;&lt;img'));
  assert.ok(html.includes('class="badge kritis"'));
});

test("renderAnswer hanya menerima status dari daftar putih (tidak ada injeksi class)", () => {
  const html = chat.renderAnswer({ answer: "x", status: 'kritis" onmouseover="x', source: "rules" });
  assert.ok(!html.includes("badge"));
  assert.ok(!html.includes("onmouseover"));
});

test("renderAnswer menandai sumber jawaban", () => {
  assert.ok(chat.renderAnswer({ answer: "a", source: "ollama" }).includes("Sumber: AI"));
  assert.ok(chat.renderAnswer({ answer: "a", source: "rules" }).includes("Sumber: Data"));
  assert.ok(chat.renderAnswer({ answer: "a", source: "offline" }).includes("Sumber: Offline"));
});

test("buildRequest memangkas pesan, riwayat, dan memvalidasi kapasitas", () => {
  const history = Array.from({ length: 9 }, (_, i) => ({ role: i % 2 ? "assistant" : "user", content: `m${i}` }));
  history.push({ role: "system", content: "disusupkan" }, { role: "user", content: "" }, null);
  const req = chat.buildRequest("x".repeat(900), history, 34000);
  assert.equal(req.message.length, 500);
  assert.equal(req.history.length, 6);
  assert.ok(req.history.every((t) => t.role === "user" || t.role === "assistant"));
  assert.equal(req.ambang_kapasitas, 34000);
  for (const bad of [0, -5, NaN, null, undefined, 1e9, "abc"]) {
    assert.equal("ambang_kapasitas" in chat.buildRequest("hai", [], bad), false, String(bad));
  }
});

test("askChat mengirim POST JSON dan mengembalikan data", async () => {
  let seen;
  const fetchImpl = async (url, init) => {
    seen = { url, init };
    return { ok: true, status: 200, json: async () => ({ data: { answer: "ok", bullets: [] } }) };
  };
  const data = await chat.askChat({ message: "halo", history: [], ambang: 34000, fetchImpl, baseUrl: "" });
  assert.equal(data.answer, "ok");
  assert.equal(seen.url, "/api/v1/chat");
  assert.equal(seen.init.method, "POST");
  assert.deepEqual(JSON.parse(seen.init.body), { message: "halo", history: [], ambang_kapasitas: 34000 });
});

test("askChat melempar ChatError dengan jenis yang tepat", async () => {
  const run = (fetchImpl) => chat.askChat({ message: "halo", fetchImpl, baseUrl: "" });
  await assert.rejects(run(fakeFetch(0, null, { throws: true })), (e) => e.kind === "network");
  await assert.rejects(run(fakeFetch(429, { detail: "Too many requests" })), (e) => e.kind === "http" && e.status === 429);
  await assert.rejects(run(fakeFetch(404, null)), (e) => e.kind === "http" && e.status === 404);
  await assert.rejects(run(fakeFetch(200, { data: {} })), (e) => e.kind === "format");
  await assert.rejects(run(fakeFetch(200, { sesuatu: 1 })), (e) => e.kind === "format");
});

test("errorMessage hanya menampilkan pesan ramah untuk 429/422", () => {
  assert.match(chat.errorMessage(new chat.ChatError("http", "x", 429)), /Terlalu banyak/);
  assert.match(chat.errorMessage(new chat.ChatError("http", "x", 422)), /tidak valid/);
  assert.equal(chat.errorMessage(new chat.ChatError("network", "detail internal")), "");
});

test("offlineAnswer memakai buildInsight dan tidak mengarang konten", () => {
  const ringkas = chat.offlineAnswer(DATA, "Ringkasan proyeksi", buildInsight);
  assert.equal(ringkas.source, "offline");
  assert.match(ringkas.answer, /Server AI tidak terjangkau/);
  assert.equal(ringkas.status, "kritis");

  const saran = chat.offlineAnswer(DATA, "apa rekomendasi operasional?", buildInsight);
  assert.ok(saran.bullets.length >= 2);
  const text = JSON.stringify([ringkas, saran]);
  for (const klaim of ["SF12", "Bukit Duri", "headway", "Zero Hallucination", "15%", "0.85"]) {
    assert.ok(!text.includes(klaim), klaim);
  }
});

test("offlineAnswer untuk bulan tertentu dan pertanyaan yang butuh server", () => {
  const des = chat.offlineAnswer(DATA, "berapa prediksi desember?", buildInsight);
  assert.match(des.answer, /Desember 2026/);
  assert.equal(des.status, "kritis");
  const musim = chat.offlineAnswer(DATA, "bagaimana pola lebaran?", buildInsight);
  assert.match(musim.answer, /backend FastAPI/);
  assert.deepEqual(musim.bullets, []);
  assert.equal(chat.offlineAnswer({ forecast: [] }, "halo", buildInsight).answer, "Data prakiraan belum tersedia.");
});
