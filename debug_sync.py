import asyncio
from app.main import api_admin_sync_template, SyncTemplateRequest

async def main():
    req = SyncTemplateRequest(company_id=2, odoo_report_id=768, report_name="Test")
    try:
        await api_admin_sync_template(req)
        print("Success")
    except Exception as e:
        print("Exception caught:", e)

asyncio.run(main())
