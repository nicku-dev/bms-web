from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import xmlrpc.client
import ssl
from app.db import SessionLocal, init_db
from app.models import User, Company
from app.config import settings

app = FastAPI(title="ISA Fleet Report - Modern View")

# Mount static files (for css, js, images if needed)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates setup
templates = Jinja2Templates(directory="app/templates")

# Initialize DB on startup
init_db()

class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    if "session_token" not in request.cookies:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/login", response_class=HTMLResponse)
async def read_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/api/login")
async def api_login(req: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username, User.is_active == True).first()
        if not user:
            return JSONResponse(status_code=401, content={"status": "error", "message": "Username tidak ditemukan atau tidak aktif."})

        authenticated = False
        
        if req.username == "admin_isa":
            if user.password == req.password:
                authenticated = True
        else:
            # XML-RPC Authentication with Odoo
            context = ssl._create_unverified_context()
            common = xmlrpc.client.ServerProxy(f'{settings.odoo_url}/xmlrpc/2/common', context=context)
            
            dbs_to_check = []
            if user.company_id:
                dbs_to_check.append(user.company.target_db_name)
            else:
                companies = db.query(Company).filter(Company.is_active == True).all()
                dbs_to_check = [c.target_db_name for c in companies]
                
            for db_name in dbs_to_check:
                try:
                    uid = common.authenticate(db_name, req.username, req.password, {})
                    if uid:
                        authenticated = True
                        break
                except Exception:
                    pass
                    
        if authenticated:
            # Set a simple cookie or return success for JS to redirect
            response = JSONResponse(content={"status": "success", "message": "Login berhasil"})
            response.set_cookie(key="session_token", value=req.username, httponly=True, max_age=86400)
            return response
        else:
            return JSONResponse(status_code=401, content={"status": "error", "message": "Password salah."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

@app.get("/api/companies")
async def api_get_companies(request: Request):
    username = request.cookies.get("session_token")
    if not username:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
        
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        companies_data = []
        if user and user.company_id:
            companies_data = [{"id": user.company.id, "name": user.company.name}]
        else:
            companies = db.query(Company).filter(Company.is_active == True).all()
            companies_data = [{"id": c.id, "name": c.name} for c in companies]
        return {"status": "success", "companies": companies_data}
    finally:
        db.close()

class ReportRequest(BaseModel):
    company_id: int
    template: str

@app.post("/api/generate_report")
async def api_generate_report(req: ReportRequest, request: Request):
    username = request.cookies.get("session_token")
    if not username:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        if not user:
            return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
            
        company = db.query(Company).filter(Company.id == req.company_id, Company.is_active == True).first()
        if not company:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Perusahaan tidak ditemukan."})
            
        # Optional: check if user is allowed to generate for this company
        if user.company_id and user.company_id != company.id:
            return JSONResponse(status_code=403, content={"status": "error", "message": "Forbidden access to this company."})
            
        # In a real app we'd fetch the report from the DB by name and company
        import os
        import re, datetime
        from app.odoo_api import OdooAPI
        from app.excel_writer import ExcelWriter
        
        # Determine year
        year_match = re.search(r'\d{4}', req.template)
        year = int(year_match.group()) if year_match else datetime.date.today().year
        date_from = f"{year}-01-01"
        date_to = f"{year}-12-31"
        
        # Hardcode odoo ID for testing if needed, or parse from template name
        # For this prototype we assume template format "Laporan Triwulan - Kapal FPS 2025 (FAST)" -> ID 1
        # Better: get from DB based on name
        from app.models import ReportTemplate
        # Try to find report in DB matching template string
        # Since frontend sends exact string, we could query it. If not found, fallback to ID 1.
        report_cfg = db.query(ReportTemplate).filter(ReportTemplate.company_id == company.id, ReportTemplate.report_name == req.template).first()
        odoo_report_id = int(report_cfg.template_format) if report_cfg else 1
        
        api = OdooAPI(db_name=company.target_db_name)
        matrix = api.generate_mis_report(odoo_report_id, date_from, date_to)
        
        clean_name = req.template.replace(' ', '_').replace('/', '_')
        output_filename = f"{clean_name}_{year}.xlsx"
        
        os.makedirs("app/static/reports", exist_ok=True)
        output_path = f"app/static/reports/{output_filename}"
        
        writer = ExcelWriter(
            output_path=output_path,
            matrix_data=matrix,
            report_name=req.template,
            company_name=company.name,
            year=year
        )
        writer.generate()
        
        return {"status": "success", "message": "Report generation finished", "file_url": f"/static/reports/{output_filename}"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()
