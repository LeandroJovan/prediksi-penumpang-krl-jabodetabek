"""
laporan_tabel.py
----------------
Mencetak tabel markdown siap-tempel untuk laporan, LANGSUNG dari artefak CSV.

Kenapa ini ada
--------------
Tabel per-horizon di laporan lama tidak bisa direproduksi: angkanya tidak
cocok dengan CSV mana pun (skala MASE yang tersirat 1.484-3.204, padahal
skala sebenarnya 1.950,69). Dengan skrip ini setiap angka di laporan bisa
dilacak ke satu baris CSV.

Pemakaian:
    python src/laporan_tabel.py              # semua tabel
    python src/laporan_tabel.py --simpan     # simpan ke reports/tabel_otomatis.md
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F_OUT = os.path.join(ROOT, "outputs")
F_REP = os.path.join(ROOT, "reports")


def _baca(nama):
    path = os.path.join(F_OUT, nama)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def md_tabel(df, index=False):
    """
    Ubah DataFrame menjadi tabel markdown tanpa dependensi `tabulate`
    (paket itu tidak terpasang di lingkungan proyek ini).
    """
    d = df.copy()
    if index:
        d = d.reset_index()

    kolom = [str(c) for c in d.columns]
    baris = []
    for _, r in d.iterrows():
        sel = []
        for v in r:
            if isinstance(v, float):
                sel.append("" if pd.isna(v) else f"{v:,.3f}".rstrip("0").rstrip("."))
            elif v is None or (isinstance(v, str) and v == ""):
                sel.append("")
            else:
                sel.append(str(v))
        baris.append(sel)

    lebar = [len(k) for k in kolom]
    for b in baris:
        for i, s in enumerate(b):
            lebar[i] = max(lebar[i], len(s))

    def garis(sel):
        return "| " + " | ".join(s.ljust(lebar[i]) for i, s in enumerate(sel)) + " |"

    out = [garis(kolom), "|" + "|".join("-" * (w + 2) for w in lebar) + "|"]
    out += [garis(b) for b in baris]
    return "\n".join(out)


def tabel_komparasi():
    df = _baca("metrik_komparasi_final.csv")
    if df is None:
        return "_(metrik_komparasi_final.csv belum ada)_"

    b = df[df["subset"] == "bersih"].sort_values("MASE")
    kol = ["model", "n", "MAE", "RMSE", "MAPE_%", "MASE"]
    kol = [k for k in kol if k in b.columns]
    return (
        "### Perbandingan model (subset bersih)\n\n"
        + b[kol].round(3).pipe(md_tabel)
        + "\n"
    )


def tabel_per_horizon():
    df = _baca("metrik_per_horizon_final.csv")
    if df is None:
        return "_(metrik_per_horizon_final.csv belum ada)_"

    b = df[df["subset"] == "bersih"]
    piv = b.pivot(index="horizon", columns="model", values="MASE")
    urut = [c for c in ["seasonal_naive", "naive", "ETS", "ETS_tanpa_musim",
                        "SARIMA", "SARIMAX", "LightGBM"] if c in piv.columns]
    piv = piv[urut]
    return (
        "### MASE per horizon (subset bersih)\n\n"
        + piv.round(3).pipe(md_tabel, index=True)
        + "\n\n_Nilai terkecil tiap baris ditandai tebal._\n\n"
        + _tandai_terkecil(piv).pipe(md_tabel, index=True)
        + "\n"
    )


def _tandai_terkecil(piv):
    """Salinan tabel dengan nilai minimum per baris diberi tanda **."""
    out = piv.round(3).astype(object)
    for idx in piv.index:
        kol = piv.loc[idx].idxmin()
        out.loc[idx, kol] = f"**{piv.loc[idx, kol]:.3f}**"
    return out


def tabel_interval():
    df = _baca("metrik_interval_conformal.csv")
    if df is None:
        return "_(metrik_interval_conformal.csv belum ada)_"

    d = df[df["level"] == 95]
    kol = ["kalibrasi", "horizon", "n_uji", "n_kalibrasi_median",
           "PICP_%", "target_%", "MPIW", "Winkler", "selisih_PICP"]
    kol = [k for k in kol if k in d.columns]
    return (
        "### Kualitas interval 95% (subset bersih)\n\n"
        + d[kol].pipe(md_tabel)
        + "\n\n_Kalibrasi 'in-sample' memakai residual yang sama untuk menyusun "
          "dan menguji interval, sehingga cakupannya bias optimis._\n"
    )


def tabel_risiko():
    df = _baca("tabel_status_risiko_kapasitas.csv")
    if df is None:
        return "_(tabel_status_risiko_kapasitas.csv belum ada)_"

    d = df.copy()
    d["bulan"] = pd.to_datetime(d["tanggal_target"]).dt.strftime("%Y-%m")
    kol = ["bulan", "y_pred_titik", "batas_atas_95", "rasio_titik_%",
           "rasio_batas_atas_%", "status_risiko"]
    kol = [k for k in kol if k in d.columns]
    return (
        "### Status risiko kapasitas\n\n"
        + d[kol].round(1).pipe(md_tabel)
        + "\n"
    )


def tabel_q_hat():
    df = _baca("q_hat_conformal.csv")
    if df is None:
        return "_(q_hat_conformal.csv belum ada)_"
    return (
        "### q_hat kalibrasi (koreksi bias + simetris)\n\n"
        + df.pipe(md_tabel)
        + "\n"
    )


def tabel_ab():
    df = _baca("uji_ab_target.csv")
    if df is None:
        return "_(uji_ab_target.csv belum ada)_"
    return (
        "### Uji A/B target peramalan\n\n"
        + df.pipe(md_tabel)
        + "\n"
    )


def tabel_importance():
    df = _baca("feature_importance_lgbm.csv")
    if df is None:
        return "_(feature_importance_lgbm.csv belum ada)_"

    piv = df.pivot(index="fitur", columns="horizon", values="gain_relatif_%")
    piv["rata2"] = piv.mean(axis=1)
    piv = piv.sort_values("rata2", ascending=False).round(1)
    return (
        "### Feature importance LightGBM (% gain)\n\n"
        + piv.pipe(md_tabel, index=True)
        + "\n"
    )


def semua_tabel():
    bagian = [
        ("## 1. Uji A/B definisi target", tabel_ab()),
        ("## 2. Perbandingan model", tabel_komparasi()),
        ("## 3. Akurasi per horizon", tabel_per_horizon()),
        ("## 4. Kualitas interval prediksi", tabel_interval()),
        ("## 5. Parameter kalibrasi (q_hat)", tabel_q_hat()),
        ("## 6. Lapisan risiko kapasitas", tabel_risiko()),
        ("## 7. Feature importance", tabel_importance()),
    ]
    judul = (
        "# Tabel Otomatis dari Artefak\n\n"
        "Dihasilkan oleh `src/laporan_tabel.py`. Jangan diedit manual:\n"
        "jalankan ulang skrip ini setelah artefak diperbarui.\n"
    )
    return judul + "\n" + "\n".join(f"{h}\n\n{t}" for h, t in bagian)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--simpan", action="store_true",
                    help="simpan ke reports/tabel_otomatis.md")
    args = ap.parse_args()

    teks = semua_tabel()

    if args.simpan:
        os.makedirs(F_REP, exist_ok=True)
        path = os.path.join(F_REP, "tabel_otomatis.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(teks)
        print(f"Tersimpan: {path}")

    print(teks)
