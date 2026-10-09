import json
from app.db import SessionLocal
from app.models import ReportTemplate

db = SessionLocal()
t = db.query(ReportTemplate).filter(ReportTemplate.report_name.ilike('%Kapal BMS 2026%')).first()
matrix = json.loads(t.skeleton_json)
if isinstance(matrix, list): matrix = matrix[0]

h0 = matrix.get('header', [])[0]
if isinstance(h0, dict): h0 = h0.get('cols', [])
h1 = matrix.get('header', [])[1]
if isinstance(h1, dict): h1 = h1.get('cols', [])

total_start = -1
for i, h in enumerate(h0):
    label = h.get('label', h.get('val', ''))
    if 'TOTAL KAPAL TERPILIH' in str(label).upper():
        total_start = sum(c.get('colspan', 1) for c in h0[:i])
        h['colspan'] = 5
        break

if total_start != -1:
    print(f"Total starts at {total_start}")
    # Fix h1
    # Remove old Q3 and YTD
    h1.pop(total_start)
    h1.pop(total_start)
    
    # Insert new Q1, Q2, Q3, Q4, YTD
    h1.insert(total_start, {'label': 'Q1', 'val': 'Q1'})
    h1.insert(total_start + 1, {'label': 'Q2', 'val': 'Q2'})
    h1.insert(total_start + 2, {'label': 'Q3', 'val': 'Q3'})
    h1.insert(total_start + 3, {'label': 'Q4', 'val': 'Q4'})
    h1.insert(total_start + 4, {'label': 'YTD', 'val': 'YTD'})
    
    # Fix body rows
    for row in matrix.get('body', []):
        cells = row.get('cells', [])
        if len(cells) > total_start:
            q3_cell = cells.pop(total_start)
            ytd_cell = cells.pop(total_start)
            
            # create empty cells based on Q3 cell style
            def create_empty(suffix):
                new_cell = q3_cell.copy()
                new_cell['val'] = 0.0
                new_cell['val_r'] = '-'
                if 'val_c' in new_cell and new_cell['val_c']:
                    new_cell['val_c'] = new_cell['val_c'].replace('.q3', '.' + suffix)
                return new_cell
                
            cells.insert(total_start, create_empty('q1'))
            cells.insert(total_start + 1, create_empty('q2'))
            cells.insert(total_start + 2, q3_cell)
            cells.insert(total_start + 3, create_empty('q4'))
            cells.insert(total_start + 4, ytd_cell)

    t.skeleton_json = json.dumps([matrix])
    db.commit()
    print("Successfully patched skeleton JSON!")
else:
    print("Could not find TOTAL KAPAL TERPILIH")
