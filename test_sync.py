import requests

payload = {
    "company_id": 1,
    "templates": [{"odoo_report_id": 104, "report_name": "Laporan Triwulan - Kapal FPS 2026 (FAST)"}]
}

try:
    r = requests.post("http://localhost:8000/api/admin/sync_templates", json=payload)
    print("Status Code:", r.status_code)
    print("Response:", r.text)
except Exception as e:
    print(e)
