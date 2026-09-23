from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="ISA Fleet Report - Modern View")

# Mount static files (for css, js, images if needed)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates setup
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def read_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/api/login")
async def api_login():
    # Placeholder for login logic using db.py models
    return {"status": "success", "token": "dummy-token"}

@app.get("/api/companies")
async def api_get_companies():
    # Placeholder for fetching companies
    return {"companies": [{"id": 1, "name": "PT Fleet Prima Samudra"}]}

@app.post("/api/generate_report")
async def api_generate_report():
    # Placeholder for Odoo API integration
    # Will use odoo_api.py and excel_writer.py
    return {"status": "success", "message": "Report generation started", "file_url": "/downloads/report.xlsx"}
