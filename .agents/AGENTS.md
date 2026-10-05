## Server Management
- Server 'dev' IP is 10.100.1.58. The hostname on the server is fr-100-091.
- The user nicku.pasaribu uses passwordless SSH to login.

## Environment Architecture
There are two instances managed in this project on the same server (10.100.1.58):

1. **SIT4 (System Integration Testing)**
   - Branch: `sit`
   - Source Code Folder: `~/srv/odoo-sit4/bms-web`
   - Port: `8501`
   - Service: `odoo-sit4.service`

2. **DEV4 (Development)**
   - Branch: `dev`
   - Source Code Folder: `~/srv/odoo-dev4/bms-web`
   - Port: `3000`
   - Service: `odoo-dev4.service`

## BMS Web Service Standards
- **Naming Convention:** All services must follow the naming format `odoo-*.service` (e.g., `odoo-sit4.service`, `odoo-dev4.service`). Do NOT use `bms-web-*.service`.
- **Placement:** Services must be placed in the system-wide folder `/etc/systemd/system/`.
- **Commands:** Use `sudo systemctl ...` to manage them.

## Production Servers (Source Data)
1. **FPS-prod:**
   - URL: `odoo-fps.lenterateknologi.com`
   - Odoo IP: `10.100.1.62`
   - Postgres IP: `10.100.1.61`

2. **BMS-prod:**
   - URL: `odoo-bms.lenterateknologi.com`
   - Odoo IP: `10.110.1.5`
   - Postgres IP: `10.100.1.61`

## FastMatrixCompiler & Odoo MIS Builder Nuances
When working on `FastMatrixCompiler` and `skeleton_json` logic in this project, adhere strictly to these rules:

1. **Variable Shadowing:** Odoo MIS Builder templates repeat the same `val_c` variable assignment (e.g., `pendapatan.q1 = ...`) for parent rows (like 'PENDAPATAN JASA') and all their child COA rows. Always ensure variables in `env_vars` are locked by the first occurrence (the parent) to prevent child rows from overwriting aggregate values.
2. **YTD Exceptions:** Static metrics like 'KAPASITAS' (ship capacity) must NOT have their YTD values aggregated/summed across quarters. YTD for these static metrics should retain the original Odoo value.
3. **Total Kapal Terpilih:** Odoo strips/corrupts formula data for the "Total Kapal Terpilih" columns. Always rebuild "Total Kapal Terpilih" columns by summing up individual ships manually within the compiler (Step 2.5) before evaluating formulas (Step 4).

## Architectural Philosophy: Odoo vs DuckDB
- **Separation of Concerns:** Odoo 18 is strictly used as the transactional source of truth (OLTP) and for storing report skeletons (`skeleton_json`). 
- **Avoid Odoo ORM for Analytics:** Do NOT attempt to run heavy aggregations or matrix calculations via Odoo XML-RPC or ORM. Odoo workers will timeout.
- **DuckDB for OLAP:** All heavy financial data (e.g., General Ledger, MIS Builder values) is synced to `app_cache.duckdb`. Always use DuckDB (via `app.engine.ReportEngine`) for fast, vectorized aggregations. The Python backend (`bms-web`) handles the heavy lifting to keep Odoo safe from CPU exhaustion.
