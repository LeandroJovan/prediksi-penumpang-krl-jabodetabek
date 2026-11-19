/* Pembuat teks "Ringkasan insight" 3 lapis.
   Murni menghitung dari data forecast + ambang kapasitas; tidak mengubah angka. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.KRLInsight = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const MON_FULL = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
  ];
  const nf0 = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 });
  const nfJuta = new Intl.NumberFormat("id-ID", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  function blnFull(ym) {
    if (!ym || typeof ym !== "string") return "-";
    const [y, m] = ym.split("-");
    const idx = Number(m) - 1;
    return `${MON_FULL[idx] || m} ${y}`;
  }

  function fmtRibu(v) {
    return v == null || Number.isNaN(Number(v)) ? "--" : nf0.format(Number(v));
  }

  function fmtJuta(v) {
    return v == null || Number.isNaN(Number(v)) ? "--" : nfJuta.format(Number(v) / 1000);
  }

  function fmtPct(v) {
    return v == null || Number.isNaN(Number(v)) ? "--" : nf1.format(Number(v));
  }

  function statusOf(u95, ambang) {
    if (u95 == null || ambang == null || Number(ambang) <= 0) {
      return { s: "belum_ditentukan", p: null };
    }
    const p = (Number(u95) / Number(ambang)) * 100;
    return { s: p >= 100 ? "kritis" : p >= 90 ? "waspada" : "aman", p };
  }

  function statusLabel(s) {
    if (s === "kritis") return "Kritis";
    if (s === "waspada") return "Waspada";
    if (s === "aman") return "Aman";
    return "Belum ditentukan";
  }

  function buildInsight(data) {
    const F = Array.isArray(data && data.forecast) ? data.forecast : [];
    const ambang = data && data.ambang_kapasitas ? data.ambang_kapasitas.nilai : null;
    const hasCapacity = ambang != null && Number(ambang) > 0;
    const rows = F.map((r) => {
      const k = statusOf(r.u95, ambang);
      return { ...r, status: k.s, rasio: k.p };
    });
    const n = rows.length;
    const kritis = rows.filter((r) => r.status === "kritis");
    const waspada = rows.filter((r) => r.status === "waspada");
    const aman = rows.filter((r) => r.status === "aman");
    const peak = rows.reduce((a, b) => (b.u95 > a.u95 ? b : a), rows[0] || null);
    const lowest = rows.reduce((a, b) => {
      if (a == null) return b;
      if (b.rasio == null) return a;
      if (a.rasio == null) return b;
      return b.rasio < a.rasio ? b : a;
    }, null);

    const technicalRows = rows.map((r) => ({
      bulan: blnFull(r.bulan),
      titik: fmtRibu(r.titik),
      l80: fmtRibu(r.l80),
      u80: fmtRibu(r.u80),
      l95: fmtRibu(r.l95),
      u95: fmtRibu(r.u95),
      rasio: r.rasio == null ? "--" : `${fmtPct(r.rasio)}%`,
      status: statusLabel(r.status),
    }));

    if (!n) {
      return {
        conclusion: "Data prediksi belum tersedia. Insight akan muncul setelah data forecast tersedia.",
        points: [],
        actions: [],
        technicalRows: [],
        counts: { kritis: 0, waspada: 0, aman: 0, total: 0 },
        peak: null,
        lowest: null,
      };
    }

    if (!hasCapacity) {
      const points = [];
      if (peak) {
        points.push({
          status: "belum_ditentukan",
          text: `Bulan paling padat: ${blnFull(peak.bulan)}. Perkiraan utama ${fmtJuta(peak.titik)} juta penumpang; skenario padat ${fmtJuta(peak.u95)} juta. Kapasitas layanan belum diatur, sehingga status risiko belum bisa ditentukan.`,
        });
      }
      points.push({
        status: "waspada",
        text: "Perkiraan masih bisa meleset cukup jauh; gunakan sebagai arahan perencanaan, bukan angka pasti.",
      });
      return {
        conclusion: "Kapasitas layanan belum diatur, sehingga status risiko belum bisa ditentukan. Perkiraan penumpang tetap dapat dilihat pada detail teknis.",
        points: points.slice(0, 3),
        actions: [
          "Lengkapi parameter kapasitas layanan agar status risiko dapat dihitung.",
          "Tinjau ulang perkiraan saat data aktual bulan baru masuk.",
        ],
        technicalRows,
        counts: { kritis: 0, waspada: 0, aman: 0, total: n },
        peak,
        lowest,
      };
    }

    let conclusion;
    if (kritis.length > 0) {
      conclusion = `${kritis.length} dari ${n} bulan ke depan diperkirakan berisiko melebihi kapasitas layanan. Puncaknya ${blnFull(peak.bulan)}.`;
    } else if (waspada.length > 0) {
      conclusion = `Tidak ada bulan yang diperkirakan melebihi kapasitas, tetapi ${waspada.length} dari ${n} bulan perlu diawasi. Puncaknya ${blnFull(peak.bulan)}.`;
    } else {
      conclusion = `Semua ${n} bulan ke depan diperkirakan masih dalam batas kapasitas.`;
    }

    const points = [];
    if (peak) {
      const cmp = peak.titik < ambang ? "di bawah" : peak.titik > ambang ? "di atas" : "setara dengan";
      points.push({
        status: peak.status,
        text: `Bulan paling padat: ${blnFull(peak.bulan)}. Perkiraan utama ${fmtJuta(peak.titik)} juta penumpang (${cmp} kapasitas ${fmtJuta(ambang)} juta); skenario padat ${fmtJuta(peak.u95)} juta (${fmtPct(peak.rasio)}% dari kapasitas).`,
      });
    }
    if (lowest) {
      let label;
      if (lowest.status === "aman") label = "Bulan yang mulai longgar";
      else if (lowest.status === "waspada") label = "Bulan yang perlu diawasi";
      else label = "Bulan dengan tekanan paling rendah";
      points.push({
        status: lowest.status,
        text: `${label}: ${blnFull(lowest.bulan)}. Skenario padat ${fmtJuta(lowest.u95)} juta (${fmtPct(lowest.rasio)}% dari kapasitas).`,
      });
    }
    points.push({
      status: "waspada",
      text: "Perkiraan masih bisa meleset cukup jauh; gunakan sebagai arahan perencanaan, bukan angka pasti.",
    });

    const actions = [];
    if (kritis.length > 0) {
      actions.push(`Tambah perjalanan atau rangkaian pada bulan Kritis, terutama ${blnFull(peak.bulan)}.`);
    }
    if (kritis.length > 0 || waspada.length > 0) {
      actions.push(`Atur arus penumpang di stasiun padat pada jam sibuk, terutama ${blnFull(peak.bulan)}.`);
    } else {
      actions.push("Pertahankan jadwal operasional dan pantau data aktual bulan baru.");
    }
    actions.push("Tinjau ulang perkiraan saat data aktual bulan baru masuk.");

    return {
      conclusion,
      points: points.slice(0, 3),
      actions: actions.slice(0, 3),
      technicalRows,
      counts: { kritis: kritis.length, waspada: waspada.length, aman: aman.length, total: n },
      peak,
      lowest,
    };
  }

  return { buildInsight, statusOf, statusLabel, blnFull, fmtRibu, fmtJuta, fmtPct };
});
