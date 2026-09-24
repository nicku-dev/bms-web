# Technical Documentation - BMS Web

Dokumen ini menjelaskan rancangan arsitektur dan teknis dari mesin laporan (Reporting Engine) khusus **BMS Web**.

## 1. Arsitektur Sistem

Aplikasi ini menggunakan pola *Monolithic API + Vanilla Frontend* dengan FastAPI sebagai tulang punggungnya.

### 1.1 Backend (Python FastAPI)
- **Framework:** `FastAPI` (Asynchronous, High Performance).
- **ORM & Database:** 
  - `SQLAlchemy` + `SQLite` (`app_config.db`) untuk data konfigurasional (User, Authentication, History, Template Laporan).
  - `DuckDB` (`app_cache.duckdb`) untuk komputasi analitik kolom dan *query tag* finansial yang rumit. Data tag mentah dari Odoo disimpan sementara (staged) di dalam *memory/disk cache* DuckDB.
- **Odoo Sync (`odoo_api.py`):** Modul `xmlrpc.client` digunakan untuk memanggil Odoo backend. Sistem akan menarik:
  - Struktur kerangka laporan (Skeleton / Matrix).
  - Data mentah finansial berdasarkan *tags* dan *companies*.
- **Report Engine (`engine.py` & `compiler.py`):** Jantung utama agregasi data. Mesin ini menguraikan matriks kosong dari Odoo dan mengisinya dengan hasil query dari DuckDB secara cepat.
- **Excel Writer (`excel_writer.py`):** Modul berbasis `xlsxwriter` yang menerjemahkan *inline style CSS* dari matriks Odoo (seperti `font-weight: bold; text-indent: 1em;`) menjadi *Excel Format Object*, lalu mengekspornya ke `.xlsx`.

### 1.2 Frontend (HTML/JS/Tailwind)
- Menggunakan pendekatan *Server-Side Rendered Templates* dengan `Jinja2` yang di-injeksi FastAPI.
- Tampilan dimodel dengan **Tailwind CSS v3** via CDN untuk *styling* cepat dan modern.
- JS (*Vanilla*) di dalam blok `<script>` HTML untuk mengatur pergerakan *Dashboard*, *fetch API*, animasi *Loading*, manipulasi tabel (*Zoom & Freeze pane*).

## 2. Struktur Database (SQLite)
File database: `app_config.db`
- **Tabel `users`**: Menyimpan username dan password yang di-*hash*.
- **Tabel `report_templates`**: Menyimpan master data laporan. Terdapat *field* `skeleton_json` yang merupakan *cache* dari *matrix body* (baris, kolom, tag, dan gaya *CSS*) dari Odoo.
- **Tabel `report_history`**: Melacak riwayat pembuatan file Excel beserta parameter (Company, Tanggal, User).

## 3. Alur Kerja (Workflow) Pembuatan Laporan
1. **User Memilih Form:** User menekan tombol "Buat Laporan" dari UI. Parameternya adalah `company_id` dan `template_id`.
2. **Hit API Backend:** UI memanggil endpoint `POST /api/generate_report`.
3. **Engine Initialization:** `ReportEngine` dipanggil di *backend*. Ia membaca *skeleton_json* dari *SQLite*.
4. **Data Fetching (DuckDB):** `FastMatrixCompiler` menganalisa semua tag ID yang dibutuhkan di laporan tersebut, lalu *menembak* query agregasi ke DuckDB (atau menarik *fresh data* dari Odoo jika data kedaluwarsa).
5. **Matrix Assembly:** Engine merakit angka-angka yang didapat ke dalam kerangka (skeleton). Sel `undefined` atau `#ERR` akan di-set `null`.
6. **Excel Generation:** Matrix hasil rakitan diserahkan ke `ExcelWriter` untuk disimpan ke `./app/static/reports/nama_file.xlsx`.
7. **History Saving:** Data path file dan log disimpan ke `report_history`.
8. **Response:** API membalas UI dengan URL Unduhan dan Matriks Data penuh.
9. **UI Rendering:** Tampilan *dashboard* merender Matriks ke dalam *Data Table* secara *real-time*.
