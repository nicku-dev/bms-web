import re
import pandas as pd
from app.engine import ReportEngine

class FastMatrixCompiler:
    def __init__(self, db_name, year, report_type='fps'):
        self.engine = ReportEngine(db_name)
        self.year = year
        self.report_type = report_type
        
        # Precompute common KPIs to memory to avoid multiple queries
        self.cache = {}
        
    def get_df_by_tag(self, tag):
        if tag not in self.cache:
            self.cache[tag] = self.engine.get_all_quarters_by_tag(self.year, tag, self.report_type)
        return self.cache[tag]

    def compile(self, matrix):
        print("🚀 FAST MATRIX COMPILER INITIATED")
        for row in matrix.get('body', []):
            label = row.get('label') or row.get('name') or ''
            
            tag_name = None
            for cell in row.get('cells', []):
                val_c = cell.get('val_c', '')
                if val_c and type(val_c) == str and 'tag_ids.name' in val_c:
                    match = re.search(r"'tag_ids\.name',\s*'=',\s*'([^']+)'", val_c)
                    if match:
                        tag_name = match.group(1)
                        break
                        
            if tag_name:
                df = self.get_df_by_tag(tag_name)
                if df is not None and not df.empty:
                    # Determine if row is a specific vessel or total
                    vessel_df = df[df['vessel_name'] == label]
                    is_total = False
                    if vessel_df.empty:
                        vessel_df = df
                        is_total = True
                        
                    # Calculate Quarters
                    q_vals = {1: 0, 2: 0, 3: 0, 4: 0}
                    for _, r in vessel_df.iterrows():
                        q = int(r['quarter'])
                        if q in q_vals:
                            q_vals[q] += float(r['value'] or 0)
                            
                    # Inject back to cells (assuming standard 5 columns: Q1, Q2, Q3, Q4, YTD)
                    if len(row.get('cells', [])) >= 5:
                        row['cells'][0]['val'] = q_vals[1]
                        row['cells'][1]['val'] = q_vals[2]
                        row['cells'][2]['val'] = q_vals[3]
                        row['cells'][3]['val'] = q_vals[4]
                        row['cells'][4]['val'] = sum(q_vals.values())
                        
                        # Fix formatting for the UI
                        for i in range(5):
                            row['cells'][i]['val_r'] = "{:,.2f}".format(row['cells'][i]['val'])
                            
        self.engine.close()
        return matrix
