# BMS Web Reporting Engine - Documentation & Savepoint

## 📌 Savepoint (Git Tag)
Proyek ini telah disimpan (di-*commit*) ke dalam Git lokal dengan nama tag:
`v1.0-dashboard-ready`

**Cara Rollback (kembali ke titik ini):**
Jika di kemudian hari Anda ingin membatalkan eksperimen atau kode menjadi rusak, cukup beri tahu model AI Anda:
> *"Tolong kembalikan / rollback kode ke tag v1.0-dashboard-ready."*
(Atau secara manual jalankan perintah `git checkout v1.0-dashboard-ready` / `git reset --hard v1.0-dashboard-ready`).

---

## 🎯 Daftar Fitur (Features List)
Aplikasi ini adalah **Enterprise Reporting Engine** khusus maritim (*Tug & Barge Operations*) yang terintegrasi dengan Odoo.
1. **Odoo Synchronization (Sync Engine)**
   - Sinkronisasi data struktur report (Skeleton) dan daftar perusahaan dari *database* Odoo secara langsung melalui *XML-RPC*.
2. **Fast Matrix Compiler**
   - Didukung oleh `DuckDB` + In-Memory Caching untuk mengurai dan merakit matriks finansial ribuan sel kurang dari 1 detik.
3. **Interactive Dashboard & Report Preview**
   - **Magnifier Zoom In/Out** dan fitur **Layar Penuh (Full Screen)** untuk memudahkan visualisasi matriks kolom yang panjang.
   - **Freeze Pane** (Uraian/Keterangan lengket di kiri) yang dinamis dan lebarnya dapat digeser (*resizable*) secara halus tanpa mematahkan tata letak (*layout*).
   - Filter pembersih (sanitizer) yang mengubah sel tidak valid seperti `#ERR` atau `undefined` menjadi kosong secara otomatis.
4. **Excel Report Generator (`excel_writer.py`)**
   - Mengekspor langsung *matrix* JSON ke `.xlsx` yang formatnya sama persis 1:1 (*pixel-perfect*) dengan tampilan Preview, lengkap dengan *indentation*, *bold*, persen, dan warna angka.
5. **Report History (Riwayat Laporan)**
   - Menyimpan jejak setiap *file* Excel yang berhasil dibuat di dalam *database* (SQLite). Anda bisa mengunduh ulang arsip secara instan (*Download History*).
6. **Admin Configuration Panel**
   - *Interface* manajemen khusus `/config` untuk melihat status sinkronisasi, daftar *template* laporan (Aktif/Tidak), dan mempratinjau detail *template* JSON asli.

---

## 🚀 Panduan Pengguna (User Guide Walkthrough)
1. **Menyalakan Sistem:** 
   - Sistem berjalan menggunakan *framework* **FastAPI** Python. 
   - Eksekusi perintah `uvicorn app.main:app --reload` di dalam direktori `bms-web`.
2. **Login Akses:** 
   - Akses via `http://localhost:8000/`. Gunakan kredensial (admin / LKT-4dm1n-!@#) untuk otentikasi.
3. **Konfigurasi (Pertama Kali):** 
   - Masuk ke tab **Konfigurasi Sistem**.
   - Klik **"Tarik Data Odoo (Sync)"** untuk menyalin kerangka *report* dari Odoo ke SQLite lokal.
4. **Membuat Laporan:** 
   - Beralih ke tab **Buat Laporan**.
   - Pilih *Perusahaan* (misal: PT. Fangiono Perkasa Sejati).
   - Pilih *Template Laporan* (misal: Laporan Triwulan Kapal).
   - Klik tombol **Buat Laporan Terpilih**. 
   - Tampilan *Preview* akan langsung muncul. Anda bisa perbesar (*zoom*) atau ubah ke Layar Penuh. File Excel (*Spreadsheet*) langsung siap diunduh di sebelah bawah. File yang sudah di-generate akan masuk ke panel "Riwayat Laporan" di samping.

---

## 💡 Best Practices: "Vibe Coding" & Transfer Konteks
Karena Anda menggunakan AI Agent (seperti Antigravity) untuk membangun sistem ini, sering kali sesi *chat* akan ditutup atau berpindah akun. Agar model AI yang baru (atau sesi baru) dapat langsung mengerti struktur proyek Anda tanpa harus menjelaskan dari nol, ikuti *best practice* berikut:

### 1. Jangan Menjelaskan Ulang, Cukup Arahkan!
Alih-alih mengetik panjang lebar menjelaskan dari awal, berikan sebuah *prompt* "Transfer Konteks" singkat kepada agen AI Anda di sesi baru:

> *"Halo, kita sedang melanjutkan proyek **BMS Web Reporting** (FastAPI, SQLite, Tailwind, Odoo XML-RPC) yang ada di folder `/Users/nickufritzie/odoo-dev-18/bms-web`. Tolong baca dokumentasi dan status saat ini di file `brain/465184e8-e558-45fd-ad61-ee24356dffb4/BMS_Web_Documentation.md` dan lihat sekilas `app/main.py`. Tujuan kita sekarang adalah [Masukkan Tugas Baru Anda]."*

### 2. Manfaatkan `<artifacts>` dan Repositori Git
* Agent Antigravity memiliki kebiasaan (dan kemampuan bawaan) untuk "melihat" dan membaca status lokal.
* Saat Anda menyuruh Agen *"lihat commit terakhir di git"* atau *"baca dokumentasi arsitektur di .md"*, Agen akan membaca kode aslinya, lalu menduplikasi pemahaman (*mental model*) yang sama dengan agen di sesi sebelumnya.
* Selalu minta agen membuatkan **Savepoint (git tag)** setiap kali suatu fitur besar telah stabil. 

### 3. Jaga "App Structure" Tetap Terbaca
Sistem ini dibuat dengan struktur modular yang sangat jelas:
- `app/main.py` : Router, API, Endpoint, HTML Render
- `app/engine.py` / `compiler.py` : Otak pembuat Matriks dan DuckDB
- `app/models.py` & `db.py` : Database SQLite
- `app/excel_writer.py` : Pengekspor XLS
- `app/templates/` : *Frontend* murni (Tailwind CSS, Javascript Vanilla).

Jika di sesi baru terjadi masalah pada UI, cukup instruksikan: *"Fokus ke `dashboard.html`, JS-nya ada di bagian bawah file."* Ini sangat menghemat token dan pikiran (*vibe check*) dari sang AI!

### 4. Instruksi Bertahap (Iterative Prompting)
Saat menggunakan Vibe Coding, jangan berikan instruksi *"Buatkan modul accounting"*. Berikan instruksi: 
- Fase 1: *"Buatkan struktur databasenya dulu (models.py), tunjukkan ke saya."*
- Fase 2: *"Bagus. Sekarang buat API GET-nya."*
- Fase 3: *"Bagus, sekarang buat UI-nya."*
Hal ini meminimalisir kemungkinan AI membuat "sampah" (*hallucinations*) di sistem yang sudah bersih ini.
