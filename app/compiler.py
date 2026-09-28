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
        
    def get_df_by_tag_and_account(self, tag, account_code):
        cache_key = f"{tag}_{account_code}"
        if cache_key not in self.cache:
            self.cache[cache_key] = self.engine.get_all_quarters_by_tag(self.year, tag, self.report_type, account_code)
        return self.cache[cache_key]

    def compile(self, matrix):
        print("🚀 FAST MATRIX COMPILER INITIATED")
        
        # 1. Map columns to vessel and quarter
        col_map = []
        if len(matrix.get('header', [])) >= 2:
            h0 = matrix['header'][0]
            h1 = matrix['header'][1]
            
            vessels = []
            for h in h0:
                colspan = h.get('colspan', 1)
                vessel_name = str(h.get('label', h.get('val', ''))).strip()
                vessels.extend([vessel_name] * colspan)
                
            for i, h in enumerate(h1):
                col_map.append({
                    'vessel_name': vessels[i] if i < len(vessels) else None,
                    'period': str(h.get('label', h.get('val', ''))).strip().lower() # 'q1', 'q2', 'q3', 'q4', 'ytd'
                })
        
        # Fallback if headers are missing (assume 5 columns Total)
        if not col_map:
            col_map = [
                {'vessel_name': 'Total', 'period': 'q1'},
                {'vessel_name': 'Total', 'period': 'q2'},
                {'vessel_name': 'Total', 'period': 'q3'},
                {'vessel_name': 'Total', 'period': 'q4'},
                {'vessel_name': 'Total', 'period': 'ytd'},
            ]

        # 2. Iterate rows
        for row in matrix.get('body', []):
            tag_name = None
            account_code = None
            
            # Try to extract account_code from row label (e.g. "4000011000 Pendapatan Usaha")
            label = str(row.get('label', '')).strip()
            acc_label_match = re.match(r'^(\d{6,12})\s+', label)
            if acc_label_match:
                account_code = acc_label_match.group(1)
                
            for cell in row.get('cells', []):
                val_c = cell.get('val_c', '')
                if val_c and type(val_c) == str:
                    tag_match = re.search(r"'tag_ids\.name',\s*'=',\s*'([^']+)'", val_c)
                    if tag_match:
                        tag_name = tag_match.group(1)
                        
                    # Also try from val_c if not found in label (just in case)
                    if not account_code:
                        acc_match = re.search(r"'account_id\.code',\s*'=like',\s*'([^']+)'", val_c)
                        if not acc_match:
                            acc_match = re.search(r"'account_id\.code',\s*'=',\s*'([^']+)'", val_c)
                        if acc_match:
                            account_code = acc_match.group(1).replace('%', '')
                        
            if tag_name or account_code:
                df = self.get_df_by_tag_and_account(tag_name, account_code)
                if df is not None and not df.empty:
                    for i, cell in enumerate(row.get('cells', [])):
                        if i >= len(col_map):
                            continue
                            
                        vessel = col_map[i]['vessel_name']
                        period = col_map[i]['period']
                        
                        vessel_df = df
                        # If the column header belongs to a specific vessel, filter it.
                        if vessel and vessel.lower() != 'total':
                            clean_vessel = vessel.replace('Kapal - ', '').strip()
                            vessel_df = df[df['vessel_name'] == clean_vessel]
                            
                            # Fallback to contains if exact match fails
                            if vessel_df.empty:
                                vessel_df = df[df['vessel_name'].str.contains(clean_vessel, regex=False, na=False)]
                        
                        val = 0
                        if period in ['q1', 'q2', 'q3', 'q4']:
                            q_num = int(period[1])
                            val = vessel_df[vessel_df['quarter'] == q_num]['value'].sum()
                        elif period == 'ytd' or period == 'total':
                            val = vessel_df['value'].sum()
                            
                        # Convert numpy float64 to python float to avoid JSON serialization errors
                        val = float(val)
                            
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f}".format(val)
                            
        self.engine.close()
        return matrix
