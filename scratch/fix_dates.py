import json
import re
from app.db import SessionLocal
from app.models import ReportTemplate

db = SessionLocal()
t = db.query(ReportTemplate).filter(ReportTemplate.report_name.ilike('%Kapal BMS 2026%')).first()
matrix = json.loads(t.skeleton_json)

h0 = matrix.get('header', [])[0]
if isinstance(h0, dict): h0 = h0.get('cols', [])
h1 = matrix.get('header', [])[1]
if isinstance(h1, dict): h1 = h1.get('cols', [])

total_start = -1
for i, h in enumerate(h0):
    label = h.get('label', h.get('val', ''))
    if 'TOTAL KAPAL TERPILIH' in str(label).upper():
        total_start = sum(c.get('colspan', 1) for c in h0[:i])
        break

if total_start != -1:
    for row in matrix.get('body', []):
        cells = row.get('cells', [])
        if len(cells) >= total_start + 4:
            # Q1 is total_start, Q2 is +1, Q4 is +3
            for offset, q_name, start_date, end_date in [
                (0, 'q1', '01-01', '03-31'),
                (1, 'q2', '04-01', '06-30'),
                (3, 'q4', '10-01', '12-31')
            ]:
                idx = total_start + offset
                c = cells[idx]
                val_c = c.get('val_c', '')
                if val_c:
                    # Fix dates
                    val_c = re.sub(r'2026-07-01', f'2026-{start_date}', val_c)
                    val_c = re.sub(r'2026-09-30', f'2026-{end_date}', val_c)
                    # Fix sumq3
                    val_c = val_c.replace('sumq3', f'sum{q_name}')
                    c['val_c'] = val_c
    
    t.skeleton_json = json.dumps(matrix)
    db.commit()
    print("Fixed dates in skeleton JSON!")
else:
    print("Could not find TOTAL KAPAL TERPILIH")
