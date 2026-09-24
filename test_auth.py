from app.odoo_api import OdooAPI
try:
    print("Mencoba autentikasi BMS_26_PRODUCTION...")
    api = OdooAPI(
        db_name="BMS_26_PRODUCTION",
        url="https://odoo-fps.lenterateknologi.com",
        username="admin",
        password="LKT-4dm1n-!@#"
    )
    print("SUCCESS! uid:", api.uid)
    
    # Try fetching mis.report.instance
    reports = api.search_read('mis.report.instance', [], ['id', 'name'])
    print("Reports found:", len(reports))
except Exception as e:
    print("FAILED:", e)
