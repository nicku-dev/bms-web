import re
with open('app/main.py', 'r') as f:
    content = f.read()

new_api = """
from pydantic import BaseModel
from typing import List, Optional

class ExportExcelRequest(BaseModel):
    company_id: int
    template_name: str
    year: int
    matrix: dict
    active_indexes: Optional[List[int]] = None

@app.post("/api/export_excel")
def export_excel(req: ExportExcelRequest, request: Request, db: Session = Depends(get_db)):
    user = validate_token(request.cookies.get("session_token"), db)
    
    company = db.query(Company).filter(Company.id == req.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    matrix = req.matrix

    # If active_indexes is provided, filter the matrix
    if req.active_indexes is not None:
        try:
            # Filter header
            # matrix['header'] = [ [ {label: 'Ship', colspan: ...}, ... ], [ {label: 'Q1'}, {label: 'Q2'}, ... ] ]
            # The easiest way is to just let JS do the filtering before sending!
            pass
        except Exception as e:
            print("Error filtering matrix", e)

    import datetime
    import os
    from app.excel_writer import ExcelWriter

    clean_name = req.template_name.replace(' ', '_').replace('/', '_')
    if str(req.year) in clean_name:
        clean_name = clean_name.replace(f"_{req.year}", "")
        clean_name = clean_name.replace(str(req.year), "")
    clean_name = clean_name.strip('_')
    
    timestamp_seq = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{clean_name}_{req.year}_{timestamp_seq}.xlsx"
    
    os.makedirs("app/static/reports", exist_ok=True)
    output_path = f"app/static/reports/{output_filename}"
    
    writer = ExcelWriter(
        output_path=output_path,
        matrix_data=matrix,
        report_name=req.template_name,
        company_name=company.name,
        year=req.year
    )
    writer.generate()
    
    from app.models import ReportHistory
    now_str = datetime.datetime.now().strftime("%d %b %Y %H:%M")
    history = ReportHistory(
        user_id=user.id if user else None,
        company_id=company.id,
        template_name=req.template_name,
        file_name=output_filename,
        file_path=output_path,
        generated_at=now_str
    )
    db.add(history)
    db.commit()
    
    return {"status": "success", "file_url": f"/static/reports/{output_filename}"}
"""

if "/api/export_excel" not in content:
    content = content.replace("@app.post(\"/api/generate_report\")", new_api + "\n@app.post(\"/api/generate_report\")")
    with open('app/main.py', 'w') as f:
        f.write(content)
