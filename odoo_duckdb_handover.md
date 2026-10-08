# Odoo DuckDB Booster - Project Memory & Handover

## Architecture Overview
The project involves replacing Odoo's native MIS Builder matrix computation with a high-performance DuckDB backend (BMS-Web).
1. **Odoo Side (`bms_duckdb_booster` addon)**: Intercepts the MIS report computation. Instead of running heavy ORM queries, it extracts the skeleton matrix (`skeleton_json`) and sends it via HTTP POST to the BMS-Web microservice.
2. **BMS-Web (`bms-web` FastAPI service)**: Receives the skeleton matrix, parses the Odoo domain expressions (e.g. `[('tag_ids.name','=','TW_PENDAPATAN JASA')]`), queries a DuckDB cache database (`app_cache.duckdb`), aggregates the values, and populates the matrix cells. It returns the populated matrix back to Odoo.
3. **Environment**:
   - Dev Server: `10.100.1.58` (Host: `fr-100-091`)
   - Target Odoo Database: `BMS_DEV2_20261005153942`
   - Target Odoo Service: `odoo-dev2.service`
   - FastAPI Booster Service: `odoo-dev4.service` (Port: 3000)

## The "Zero Data" Bug & Resolution

### Symptoms
The Odoo UI preview for the MIS Report (`Triwulan - Kapal BMS 2026`) showed exactly `0.0` for all cells, even though backend logs and DuckDB scripts confirmed the calculation successfully yielded large figures (e.g., ~430 Billion for PENDAPATAN JASA).

### Root Cause
The problem existed in the data injection loop within Odoo's `odoo_addons/bms_duckdb_booster/models/mis_report_instance.py`:
1. The FastAPI endpoint (`/api/odoo/compute_booster_direct`) was correctly calculating and returning the fully populated matrix dictionary directly as the root JSON object (e.g., `{"body": [...], "header": [...]}`).
2. However, the Odoo Python code was unpacking it as: 
   `compiled_matrix = response.json().get('data', {})`
3. Because there was no `"data"` key in the API response, `compiled_matrix` became an empty dictionary `{}`.
4. Consequently, the row injection loop was completely skipped, leaving Odoo's native `0.0` values unchanged in the UI.

### The Fix Applied
In `odoo_addons/bms_duckdb_booster/models/mis_report_instance.py` (Line ~92), the payload extraction was corrected to:
```python
if response.status_code == 200:
    compiled_matrix = response.json()
```
This fix was applied both locally and directly on the server (`10.100.1.58`). Automated testing via `odoo-bin shell` confirms the matrix cells are now correctly populated with the DuckDB values (e.g., `val=6126750000.0, val_r=6,126,750,000.00`).

### Why the UI Hasn't Changed Yet
Although the Python file `mis_report_instance.py` was fixed on the server, **the Odoo process (`odoo-dev2.service`) must be restarted for the Python changes to take effect in RAM.** 
The previous agent attempted to restart it but was blocked because the `sudo systemctl restart odoo-dev2.service` command requires the `nicku.pasaribu` sudo password.

## Next Steps for the User / Next Agent
1. **Restart Odoo**: SSH into the server (`10.100.1.58`) and manually restart the Odoo service to load the Python fix:
   `sudo systemctl restart odoo-dev2.service`
2. **Verify UI**: Check the MIS Report preview in Odoo. The values should now correctly reflect the DuckDB computations.
3. **Commit Changes**: The local workspace changes in `odoo_addons/bms_duckdb_booster/models/mis_report_instance.py` should be committed to git.

## Agent Recommendation
For this complex code architecture involving multiple microservices, remote SSH execution, and deep Odoo ORM logic, **Claude 3.5 Sonnet** is currently the best and most capable model in the Antigravity ecosystem. It excels at fast context retrieval and intricate Python debugging.
