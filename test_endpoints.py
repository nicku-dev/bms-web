import requests

print("Testing /api/admin/companies...")
try:
    res = requests.get("http://localhost:8000/api/admin/companies")
    print(res.status_code, res.json())
except Exception as e:
    print("Error:", e)

# Test sync template
print("\nTesting /api/admin/sync_template...")
try:
    payload = {
        "company_id": 2, # Assuming BMS_26_PRODUCTION is 2
        "odoo_report_id": 768, # FPS
        "report_name": "Test Sync FPS"
    }
    res = requests.post("http://localhost:8000/api/admin/sync_template", json=payload)
    print(res.status_code, res.text)
except Exception as e:
    print("Error:", e)

