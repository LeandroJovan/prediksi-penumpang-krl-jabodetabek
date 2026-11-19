/* Klien chat KRL Insight.
   - Server mengirim TEKS POLOS; semua teks (jawaban server maupun input pengguna) di-escape sebelum masuk DOM.
   - Bila server tidak terjangkau, jawaban offline hanya diturunkan dari data.json lewat KRLInsight.buildInsight
     (tidak ada angka atau saran yang ditulis tangan di sini). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.KRLChat = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const STATUS = ["aman", "waspada", "kritis", "belum_ditentukan"];
  const STATUS_LABEL = { aman: "Aman", waspada: "Waspada", kritis: "Kritis", belum_ditentukan: "Belum ditentukan" };
  const MAX_HISTORY = 6;
  const MAX_MESSAGE = 500;
  const MON = ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober", "november", "desember"];
  const MON_FULL = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function statusBadge(status) {
    if (STATUS.indexOf(status) < 0) return "";
    return `<span class="badge ${status}">${STATUS_LABEL[status].toUpperCase()}</span>`;
  }

  function renderSuggestions(list) {
    const items = (Array.isArray(list) ? list : []).slice(0, 4).filter((s) => typeof s === "string" && s);
    if (!items.length) return "";
    return `<div class="chat-sugg">${items
      .map((s) => `<button type="button" class="chip-btn" data-q="${escapeHtml(s)}">${escapeHtml(s)}</button>`)
      .join("")}</div>`;
  }

  /* data: {answer, bullets[], status, source, suggestions[]} -> HTML aman */
  function renderAnswer(data) {
    const d = data || {};
    const bullets = Array.isArray(d.bullets) ? d.bullets : [];
    const sourceLabel = d.source === "ollama" ? "AI" : d.source === "offline" ? "Offline" : "Data";
    const sourceTitle =
      d.source === "ollama" ? "Dijawab model bahasa, angka sudah diverifikasi terhadap data"
        : d.source === "offline" ? "Server tidak terjangkau; jawaban terbatas dari data.json"
          : "Dijawab langsung dari data dan perhitungan sistem";
    return (
      `<p>${escapeHtml(d.answer)} ${statusBadge(d.status)}</p>` +
      (bullets.length ? `<ul>${bullets.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul>` : "") +
      `<div class="src-tag" title="${escapeHtml(sourceTitle)}">Sumber: ${sourceLabel}</div>` +
      renderSuggestions(d.suggestions)
    );
  }

  function buildRequest(message, history, ambang) {
    const text = String(message == null ? "" : message).trim().slice(0, MAX_MESSAGE);
    const turns = (Array.isArray(history) ? history : [])
      .filter((t) => t && (t.role === "user" || t.role === "assistant") && typeof t.content === "string" && t.content)
      .slice(-MAX_HISTORY)
      .map((t) => ({ role: t.role, content: t.content.slice(0, 1000) }));
    const body = { message: text, history: turns };
    const cap = Number(ambang);
    if (Number.isFinite(cap) && cap > 0 && cap <= 1000000) body.ambang_kapasitas = cap;
    return body;
  }

  class ChatError extends Error {
    constructor(kind, message, status) {
      super(message);
      this.name = "ChatError";
      this.kind = kind; // "network" | "http" | "format"
      this.status = status;
    }
  }

  /* Memanggil backend. Melempar ChatError agar pemanggil bisa jatuh ke jawaban offline. */
  async function askChat(opts) {
    const o = opts || {};
    const fetchImpl = o.fetchImpl || (typeof fetch !== "undefined" ? fetch : null);
    if (!fetchImpl) throw new ChatError("network", "fetch tidak tersedia");
    const base = o.baseUrl != null ? o.baseUrl : (typeof window !== "undefined" && window.KRL_API_BASE) || "";
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), o.timeoutMs || 20000) : null;
    let response;
    try {
      response = await fetchImpl(`${base}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildRequest(o.message, o.history, o.ambang)),
        signal: controller ? controller.signal : undefined,
      });
    } catch (err) {
      throw new ChatError("network", err && err.message ? err.message : "gagal terhubung");
    } finally {
      if (timer) clearTimeout(timer);
    }
    if (!response.ok) {
      let detail = "";
      try { detail = (await response.json()).detail || ""; } catch (_) { /* abaikan */ }
      throw new ChatError("http", typeof detail === "string" ? detail : "permintaan ditolak", response.status);
    }
    let body;
    try { body = await response.json(); } catch (_) { throw new ChatError("format", "respons bukan JSON"); }
    if (!body || !body.data || typeof body.data.answer !== "string") throw new ChatError("format", "respons tidak sesuai kontrak");
    return body.data;
  }

  /* Pesan kesalahan ramah untuk ditampilkan; tidak membocorkan detail teknis. */
  function errorMessage(err) {
    if (err && err.kind === "http" && err.status === 429) return "Terlalu banyak pertanyaan. Coba lagi sebentar lagi.";
    if (err && err.kind === "http" && err.status === 422) return "Pertanyaan tidak valid. Gunakan teks singkat (maksimal 500 karakter).";
    return "";
  }

  function blnFull(ym) {
    const [y, m] = String(ym).split("-");
    return `${MON_FULL[Number(m) - 1] || m} ${y}`;
  }

  /* Jawaban offline: hanya dari data.json lewat buildInsight. Pertanyaan yang butuh server dijelaskan apa adanya. */
  function offlineAnswer(data, message, buildInsight) {
    const q = String(message || "").toLowerCase();
    const note = "Server AI tidak terjangkau, jadi jawaban dibatasi pada data di dashboard.";
    const suggestions = ["Ringkasan proyeksi 6 bulan ke depan", "Bagaimana analisis risiko kapasitas?", "Apa rekomendasi operasional?"];
    const F = (data && data.forecast) || [];
    if (!F.length) return { answer: "Data prakiraan belum tersedia.", bullets: [], status: null, source: "offline", suggestions };

    const monthIdx = MON.findIndex((m) => q.includes(m));
    if (monthIdx >= 0) {
      const row = F.find((r) => Number(String(r.bulan).split("-")[1]) === monthIdx + 1);
      if (row) {
        const cap = data.ambang_kapasitas && data.ambang_kapasitas.nilai;
        const util = cap ? (row.u95 / cap) * 100 : null;
        const status = util == null ? "belum_ditentukan" : util >= 100 ? "kritis" : util >= 90 ? "waspada" : "aman";
        const f = (v) => new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 }).format(v);
        return {
          answer: `Prakiraan ${blnFull(row.bulan)}: status ${STATUS_LABEL[status]}.`,
          bullets: [
            `Perkiraan utama: ${f(row.titik)} ribu penumpang.`,
            `Skenario cukup padat (80%): ${f(row.l80)} s.d. ${f(row.u80)} ribu.`,
            `Skenario padat (95%): ${f(row.l95)} s.d. ${f(row.u95)} ribu.`,
          ],
          status,
          source: "offline",
          suggestions,
        };
      }
    }
    if (typeof buildInsight !== "function") return { answer: note, bullets: [], status: null, source: "offline", suggestions };
    const ins = buildInsight(data);
    const status = ins.counts.kritis ? "kritis" : ins.counts.waspada ? "waspada" : ins.counts.aman ? "aman" : "belum_ditentukan";
    if (/(rekomendasi|saran|langkah|tindakan|mitigasi)/.test(q)) {
      return { answer: `${note} Rekomendasi mengikuti status risiko saat ini.`, bullets: ins.actions, status, source: "offline", suggestions };
    }
    if (/(lebaran|musim|pola|hari kerja|covid|pandemi|interval|skenario|kapasitas (naik|turun|dinaik|diturun)|bagaimana jika)/.test(q)) {
      return {
        answer: `${note} Pertanyaan ini perlu dihitung dari data riwayat di server; jalankan backend FastAPI untuk jawaban lengkap.`,
        bullets: [],
        status: null,
        source: "offline",
        suggestions,
      };
    }
    return { answer: `${note} ${ins.conclusion}`, bullets: ins.points.map((p) => p.text), status, source: "offline", suggestions };
  }

  return { escapeHtml, renderAnswer, renderSuggestions, buildRequest, askChat, errorMessage, offlineAnswer, ChatError };
});
