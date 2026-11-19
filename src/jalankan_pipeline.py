"""
jalankan_pipeline.py
--------------------
Menjalankan notebook pipeline secara berurutan dari command line,
sehingga artefak bisa diregenerasi tanpa membuka Jupyter.

Pemakaian:
    python src/jalankan_pipeline.py 01 03 04 05 06
    python src/jalankan_pipeline.py --semua

Setiap notebook dieksekusi di dalam folder notebooks/ (sesuai asumsi
path relatif di notebook), dan berhenti pada error pertama.
"""

import argparse
import glob
import os
import subprocess
import sys
import time

import nbformat
from nbclient import NotebookClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER_NOTEBOOK = os.path.join(ROOT, "notebooks")


def daftar_notebook():
    pola = os.path.join(FOLDER_NOTEBOOK, "*.ipynb")
    hasil = []
    for p in sorted(glob.glob(pola)):
        nama = os.path.basename(p)
        if nama.startswith("."):
            continue
        hasil.append(nama)
    return hasil


def jalankan(nama_file, timeout=1800):
    path = os.path.join(FOLDER_NOTEBOOK, nama_file)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Notebook tidak ditemukan: {path}")

    print(f"\n{'=' * 70}\n>>> {nama_file}\n{'=' * 70}", flush=True)
    mulai = time.time()

    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        resources={"metadata": {"path": FOLDER_NOTEBOOK}},
        allow_errors=False,
    )
    client.execute()

    nbformat.write(nb, path)  # simpan output ke notebook
    print(f"<<< selesai dalam {time.time() - mulai:.1f} detik", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("notebooks", nargs="*", help="Nomor atau nama notebook")
    ap.add_argument("--semua", action="store_true", help="Jalankan semua notebook")
    args = ap.parse_args()

    semua = daftar_notebook()

    if args.semua:
        target = [n for n in semua if n[:2].isdigit()]
    else:
        target = []
        for t in args.notebooks:
            cocok = [n for n in semua if n.startswith(t)]
            if not cocok:
                print(f"Tidak ada notebook yang cocok dengan '{t}'")
                sys.exit(1)
            target.append(cocok[0])

    if not target:
        print("Tidak ada notebook yang dijalankan.")
        sys.exit(0)

    print("Akan dijalankan:", target)
    for n in target:
        jalankan(n)

    print("\nSelesai semua.")
