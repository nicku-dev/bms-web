# BMS Web Reporting Engine

Aplikasi web berbasis **FastAPI** dan **DuckDB** yang berfungsi sebagai mesin agregator dan generator laporan finansial (*Tug & Barge Operations*) yang terintegrasi langsung dengan Odoo.

## ✨ Fitur Utama
- **XML-RPC Sync:** Mengunduh dan mengsinkronisasi master data (Perusahaan) dan kerangka (Skeleton) laporan dari Odoo.
- **Fast Matrix Compiler:** Menggunakan `DuckDB` *in-memory* untuk komputasi ratusan tag formula laporan Odoo (kurang dari 1 detik).
- **Interactive UI (Dashboard):** 
  - Dibangun dengan **Tailwind CSS**.
  - Mendukung pratinjau interaktif (Zoom & Layar Penuh)
  - Fitur *Freeze Pane* untuk kemudahan navigasi kolom matriks finansial.
- **Excel Exporter:** Pembuatan file Excel `.xlsx` yang formatnya (*styling*, warna, *bold*, *indent*) sama persis dengan yang ada di Odoo.
- **History System:** Seluruh hasil ekspor Excel diarsipkan dan dapat diunduh ulang kapan saja melalui panel riwayat.

## 📂 Struktur Direktori
- `app/` : Source code utama aplikasi (FastAPI router, engine, db models).
- `docs/` : Panduan teknis dan manual pengguna (Baca [docs/USER_GUIDE.md](docs/USER_GUIDE.md)).
- `scripts/` : Kumpulan *script testing* dan perkakas *maintenance* *database*.
- `app_config.db` : SQLite database untuk konfigurasi (users, templates, history).
- `app_cache.duckdb` : DuckDB persistent file (cache & komputasi data besar).

## 🚀 Instalasi & Menjalankan Aplikasi
1. Pastikan terinstall **Python 3.10+**.
2. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```
3. Jalankan server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. Akses `http://localhost:8000` di *browser*. (Login default yang disediakan administrator).

---
*Dikembangkan menggunakan bantuan Vibe Coding (Antigravity).*
