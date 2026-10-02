import re
import pandas as pd
from app.engine import ReportEngine
from types import SimpleNamespace

from app.compiler_fetcher import CompilerFetcher
from app.compiler_evaluator import CompilerEvaluator

class FastMatrixCompiler:
    def __init__(self, db_name, year, report_type='fps', odoo_report_id=None):
        self.engine = ReportEngine(db_name)
        self.year = year
        self.report_type = report_type
        self.odoo_report_id = odoo_report_id
        
        # 1. Isolate Fetcher
        self.fetcher = CompilerFetcher(self.engine, year, report_type)
        
        # 2. Fetch MIS Report Queries as Objects for eval()
        self.query_vars = {}
        if self.odoo_report_id:
            queries_data = self.engine.get_mis_report_queries(self.odoo_report_id)
            for q_name, q_fields in queries_data.items():
                self.query_vars[q_name] = SimpleNamespace(**q_fields)
                
        # 3. Isolate Evaluator
        self.evaluator = CompilerEvaluator(self.query_vars)

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
                    'period': str(h.get('label', h.get('val', ''))).strip().lower()
                })
        
        tpj_semua = self.engine.get_kpi_tpj_semua(self.year)
        
        env_vars = [{} for _ in range(len(col_map))]

        # STEP 1 & 2: Process direct accounting queries and tag filters
        for row in matrix.get('body', []):
            label = str(row.get('label', '')).upper()
            
            tag_name = None
            account_code = None
            
            tag_match = re.search(r'#(.*?)#', label)
            if tag_match:
                tag_name = tag_match.group(1).replace('%', '')
                
            if not tag_name:
                acc_match = re.search(r'^(\d+)', label)
                if acc_match:
                    account_code = acc_match.group(1).replace('%', '')

            if not tag_name and not account_code:
                if label == 'TRIP' or label == 'TRIP KAPAL':
                    df = self.fetcher.get_kpi_trip()
                elif label == 'KAPASITAS' or label == 'KAPASITAS KAPAL':
                    df = self.fetcher.get_kpi_kapasitas()
                else:
                    df = None
            elif tag_name or account_code:
                df = self.fetcher.get_df_by_tag_and_account(tag_name, account_code)
            else:
                df = None

            if df is not None and not df.empty:
                for i, cell in enumerate(row.get('cells', [])):
                    if i >= len(col_map):
                        continue
                        
                    vessel = col_map[i]['vessel_name']
                    period = col_map[i]['period']
                    
                    if not vessel:
                        continue
                        
                    is_expense = False
                    if 'BIAYA' in label or 'BEBAN' in label:
                        is_expense = True
                    elif account_code and str(account_code)[0] in ['5', '6', '7', '8', '9']:
                        is_expense = True
                        
                    val = cell.get('val', 0.0)
                    if 'total' not in vessel.lower():
                        clean_vessel = vessel.replace('Kapal - ', '').strip()
                        vessel_df = df[df['vessel_name'] == clean_vessel]
                        
                        # Fallback to contains if exact match fails
                        if vessel_df.empty:
                            vessel_df = df[df['vessel_name'].str.contains(clean_vessel, regex=False, na=False)]
                            
                        if not vessel_df.empty:
                            if period in ['q1', 'q2', 'q3', 'q4']:
                                q_num = int(period[1])
                                val = vessel_df[vessel_df['quarter'] == q_num]['value'].sum()
                            elif period == 'ytd' or period == 'total':
                                val = vessel_df['value'].sum()
                                
                        try:
                            val = float(val)
                            if is_expense:
                                val = -abs(val)
                        except (ValueError, TypeError):
                            val = 0.0
                            
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"

        # STEP 3: Store variables to env_vars for step 4
        for row in matrix.get('body', []):
            label = str(row.get('label', '')).upper()
            for i, cell in enumerate(row.get('cells', [])):
                if i >= len(col_map):
                    continue
                    
                val_c = str(cell.get('val_c', ''))
                if '=' in val_c and '[' not in val_c:
                    parts = val_c.split('=', 1)
                    if len(parts) == 2:
                        var_name = parts[0].strip()
                        # Some names have prefixes (e.g. tpj.balp), strip them for env var name
                        var_name_clean = var_name.split('.')[0]
                        env_vars[i][var_name_clean] = cell.get('val', 0.0)
                        env_vars[i][var_name] = cell.get('val', 0.0)

                if 'TPJ' in label and 'TOTAL PENDAPATAN JASA' in label:
                    env_vars[i]['tpj'] = cell.get('val', 0.0)

        # Build tpj_semua values to the environment
        if not tpj_semua.empty:
            for i, col in enumerate(col_map):
                period = col['period']
                if period in ['q1', 'q2', 'q3', 'q4']:
                    q_num = int(period[1])
                    val = tpj_semua[tpj_semua['quarter'] == q_num]['value'].sum()
                    env_vars[i]['tpj_semua'] = val
                elif period == 'ytd' or period == 'total':
                    env_vars[i]['tpj_semua'] = tpj_semua['value'].sum()
                    
                tpj = env_vars[i].get('tpj', 0.0)
                tpj_s = env_vars[i].get('tpj_semua', 0.0)
                if tpj_s != 0:
                    env_vars[i]['prop_tpj'] = tpj / tpj_s
                else:
                    env_vars[i]['prop_tpj'] = 0.0

        # Proporsional TPJ row insertion logic
        for row in matrix.get('body', []):
            label = str(row.get('label', '')).upper()
            if 'TPJ SEMUA KAPAL BMS' in label:
                for i, cell in enumerate(row.get('cells', [])):
                    if i < len(env_vars):
                        val = env_vars[i].get('tpj_semua', 0.0)
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"
            
            elif 'PROPORSIONAL TPJ' in label:
                for i, cell in enumerate(row.get('cells', [])):
                    if i < len(env_vars):
                        val = env_vars[i].get('prop_tpj', 0.0)
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f} %".format(val * 100) if abs(val) >= 0.00005 else "-"

            # MARGIN LABA logic
            elif 'MARGIN' in label and 'LABA' in label:
                laba_cells = []
                pendapatan_cells = []
                for search_row in matrix.get('body', []):
                    sl = str(search_row.get('label', '')).upper()
                    if sl == 'LABA (RUGI) BERSIH' or sl == 'LABA BERSIH':
                        laba_cells = search_row.get('cells', [])
                    if 'TOTAL PENDAPATAN JASA' in sl:
                        pendapatan_cells = search_row.get('cells', [])
                        
                if laba_cells and pendapatan_cells:
                    for i, cell in enumerate(row.get('cells', [])):
                        laba = laba_cells[i].get('val', 0.0) if i < len(laba_cells) else 0.0
                        pendapatan = pendapatan_cells[i].get('val', 0.0) if i < len(pendapatan_cells) else 0.0
                        
                        try:
                            laba = float(laba)
                        except (ValueError, TypeError):
                            laba = 0.0
                            
                        try:
                            pendapatan = float(pendapatan)
                        except (ValueError, TypeError):
                            pendapatan = 0.0
                            
                        val = 0.0
                        if pendapatan != 0:
                            val = (laba / pendapatan)
                            
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f} %".format(val * 100) if abs(val) >= 0.00005 else "-"

        # STEP 4: Evaluate Algebraic Formulas with ISOLATED Evaluator
        for _ in range(3):
            for row in matrix.get('body', []):
                label_upper = str(row.get('label', '')).upper()
                
                # Prevent Odoo algebraic formulas from overwriting KPI data
                if label_upper in ['KAPASITAS', 'KAPASITAS KAPAL', 'TRIP', 'TRIP KAPAL']:
                    continue
                    
                is_expense = ('BIAYA' in label_upper or 'BEBAN' in label_upper or 'PENYUSUTAN' in label_upper)
                
                for i, cell in enumerate(row.get('cells', [])):
                    if i >= len(col_map):
                        continue
                        
                    val_c = str(cell.get('val_c', ''))
                    
                    # Evaluate if it's an assignment like "var = expr" and not an Odoo domain list "['...']"
                    if '=' in val_c and '[' not in val_c and 'balp' not in val_c and 'tpj_skf' not in val_c and 'sumq1' not in val_c:
                        parts = val_c.split('=', 1)
                        if len(parts) == 2:
                            expr = parts[1].strip()
                            
                            try:
                                # USE THE ISOLATED EVALUATOR
                                val = self.evaluator.evaluate_algebraic(expr, env_vars[i], is_expense)
                            except ValueError:
                                # DO NOT overwrite if evaluation fails cleanly!
                                continue
                                
                            # Format as percentage if it contains % or persentase
                            if '%' in label_upper or 'PERSENTASE' in label_upper:
                                cell['val'] = val
                                cell['val_r'] = "{:,.2f} %".format(val * 100) if abs(val) >= 0.00005 else "-"
                            else:
                                cell['val'] = val
                                cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"
                                
        return matrix
