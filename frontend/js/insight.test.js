const test = require("node:test");
const assert = require("node:assert/strict");
const { buildInsight } = require("./insight.js");

const MONTHS = ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02"];

function makeData(points, uppers, capacity = 34000) {
  return {
    ambang_kapasitas: { nilai: capacity },
    forecast: points.map((point, index) => ({
      bulan: MONTHS[index],
      titik: point,
      l80: point - 500,
      u80: point + 500,
      l95: point - 1000,
      u95: uppers[index],
    })),
  };
}

test("5 dari 6 bulan Kritis memakai struktur 3 lapis", () => {
  const data = makeData(
    [30000, 31000, 30500, 32000, 30000, 29000],
    [34000, 35000, 34500, 36000, 34000, 33000],
  );
  const insight = buildInsight(data);
  assert.match(insight.conclusion, /5 dari 6/);
  assert.match(insight.conclusion, /Desember 2026/);
  assert.equal(insight.points.length, 3);
  assert.equal(insight.points[0].status, "kritis");
  assert.match(insight.points[0].text, /Perkiraan utama/);
  assert.match(insight.points[0].text, /skenario padat/);
  assert.match(insight.points[0].text, /di bawah kapasitas/);
  assert.match(insight.points[0].text, /32,0 juta/);
  assert.match(insight.points[0].text, /36,0 juta/);
  assert.match(insight.points[0].text, /105,9%/);
  assert.ok(insight.actions.length >= 2 && insight.actions.length <= 3);
  assert.equal(insight.technicalRows.length, 6);
});

test("semua bulan Aman memberi kesimpulan yang menenangkan", () => {
  const data = makeData([28000, 28000, 28000, 28000, 28000, 28000], [30000, 30000, 30000, 30000, 30000, 30000]);
  const insight = buildInsight(data);
  assert.match(insight.conclusion, /Semua 6 bulan/);
  assert.match(insight.conclusion, /batas kapasitas/);
  assert.doesNotMatch(insight.conclusion, /Kritis/);
  assert.equal(insight.points[0].status, "aman");
  assert.ok(insight.actions.length >= 2 && insight.actions.length <= 3);
});

test("data prediksi kosong tidak membuat error", () => {
  const insight = buildInsight({ forecast: [], ambang_kapasitas: { nilai: 34000 } });
  assert.match(insight.conclusion, /belum tersedia/);
  assert.deepEqual(insight.points, []);
  assert.deepEqual(insight.actions, []);
  assert.deepEqual(insight.technicalRows, []);
});

test("kapasitas belum diatur ditangani eksplisit", () => {
  const data = makeData([30000, 31000, 30500, 32000, 30000, 29000], [34000, 35000, 34500, 36000, 34000, 33000], null);
  const insight = buildInsight(data);
  assert.match(insight.conclusion, /Kapasitas layanan belum diatur/);
  assert.equal(insight.points[0].status, "belum_ditentukan");
  assert.ok(insight.actions.length >= 2 && insight.actions.length <= 3);
});
