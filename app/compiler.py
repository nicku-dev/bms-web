import re
import pandas as pd
from app.engine import ReportEngine

from types import SimpleNamespace

class FastMatrixCompiler:
    def __init__(self, db_name, year, report_type='fps', odoo_report_id=None):
        self.engine = ReportEngine(db_name)
        self.year = year
        self.report_type = report_type
        self.odoo_report_id = odoo_report_id
        
        # Fetch MIS Report Queries as Objects for eval()
        self.query_vars = {}
        if self.odoo_report_id:
            queries_data = self.engine.get_mis_report_queries(self.odoo_report_id)
            for q_name, q_fields in queries_data.items():
                self.query_vars[q_name] = SimpleNamespace(**q_fields)
        
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

        # Environment for evaluating algebraic formulas (one dict per column)
        env_vars = [{} for _ in col_map]

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
                val_c = str(cell.get('val_c', ''))
                
                # Default initialize df
                df = pd.DataFrame()
                if val_c and type(val_c) == str:
                    tag_match = re.search(r"['\"]tag_ids\.name['\"],\s*['\"]=like['\"],\s*['\"]([^'\"]+)['\"]", val_c)
                    if not tag_match:
                        tag_match = re.search(r"['\"]tag_ids\.name['\"],\s*['\"]=[\"'],\s*['\"]([^'\"]+)['\"]", val_c)
                    if tag_match:
                        tag_name = tag_match.group(1)
                        
                    # Also try from val_c if not found in label (just in case)
                    if not account_code:
                        acc_match = re.search(r"['\"]account_id\.code['\"],\s*['\"]=like['\"],\s*['\"]([^'\"]+)['\"]", val_c)
                        if not acc_match:
                            acc_match = re.search(r"['\"]account_id\.code['\"],\s*['\"]=[\"'],\s*['\"]([^'\"]+)['\"]", val_c)
                        if acc_match:
                            account_code = acc_match.group(1).replace('%', '')
                            
            if not tag_name and not account_code:
                if label.upper() == 'TRIP' or label.upper() == 'TRIP KAPAL':
                    df = self.engine.get_kpi_trip(self.year, self.report_type)
                elif label.upper() == 'KAPASITAS' or label.upper() == 'KAPASITAS KAPAL':
                    df = self.engine.get_kpi_kapasitas(self.year, self.report_type)
            elif tag_name or account_code:
                df = self.get_df_by_tag_and_account(tag_name, account_code)
                
            if df is not None and not df.empty:
                    for i, cell in enumerate(row.get('cells', [])):
                        if i >= len(col_map):
                            continue
                            
                        vessel = col_map[i]['vessel_name']
                        period = col_map[i]['period']
                        
                        is_expense = False
                        label_upper = str(row.get('label', '')).upper()
                        if 'BIAYA' in label_upper or 'BEBAN' in label_upper:
                            is_expense = True
                        elif account_code and str(account_code)[0] in ['5', '6', '7', '8', '9']:
                            is_expense = True
                            
                        val = cell.get('val', 0.0)
                        if vessel and 'total' not in vessel.lower():
                            vessel_df = df
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
                            except:
                                val = 0.0
                            if is_expense:
                                val = -val
                        else:
                            # It's a Total column (e.g., 'Total Kapal Terpilih')
                            # Sum all preceding cells in this row that have the same period and are NOT a total column
                            val = sum(
                                row.get('cells', [])[j].get('val', 0.0)
                                for j in range(i)
                                if col_map[j]['period'] == period and 'total' not in col_map[j]['vessel_name'].lower()
                            )
                            val = float(val)
                            
                        # Save to env_vars for algebraic formulas later
                        if row.get('cells') and i < len(row['cells']):
                            val_c_for_var = str(row['cells'][i].get('val_c', ''))
                            if '=' in val_c_for_var:
                                var_name_step2 = val_c_for_var.split('=')[0].split('.')[0].strip()
                                if var_name_step2 and var_name_step2 not in env_vars[i]:
                                    env_vars[i][var_name_step2] = val
                                    
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"
                        
        # 3. Post-process pure formula rows (TPJ)
        # Grab PENDAPATAN JASA cells to copy into TPJ Per Kapal
        pendapatan_jasa_cells = None
        total_pendapatan_jasa_cells = None
        laba_rugi_bersih_cells = None
        
        for row in matrix.get('body', []):
            label = str(row.get('label', '')).strip().upper()
            if label == 'PENDAPATAN JASA' or label == 'TW_PENDAPATAN JASA':
                pendapatan_jasa_cells = row.get('cells', [])
            elif label == 'TOTAL PENDAPATAN JASA':
                total_pendapatan_jasa_cells = row.get('cells', [])
            elif label == 'LABA (RUGI) BERSIH':
                laba_rugi_bersih_cells = row.get('cells', [])

        # Fetch True TPJ Semua Kapal from DuckDB
        tpj_semua_df = self.engine.get_kpi_tpj_semua(self.year)

        for row in matrix.get('body', []):
            label = str(row.get('label', '')).strip()
            if 'TPJ Per Kapal' in label:
                for i, cell in enumerate(row.get('cells', [])):
                    if pendapatan_jasa_cells and i < len(pendapatan_jasa_cells):
                        val = pendapatan_jasa_cells[i].get('val', 0.0)
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f}".format(float(val)) if abs(float(val)) >= 0.005 else "-"
            
            elif 'TPJ Semua Kapal' in label:
                for i, cell in enumerate(row.get('cells', [])):
                    if i < len(col_map):
                        period = col_map[i]['period'].lower()
                        val = 0.0
                        if period in ['q1', 'q2', 'q3', 'q4']:
                            q_num = int(period[1])
                            if not tpj_semua_df.empty:
                                val = tpj_semua_df[tpj_semua_df['quarter'] == q_num]['value'].sum()
                        else:
                            if not tpj_semua_df.empty:
                                val = tpj_semua_df['value'].sum()
                                
                        cell['val'] = float(val)
                        cell['val_r'] = "{:,.2f}".format(float(val)) if abs(float(val)) >= 0.005 else "-"
                        
            elif 'Proportional TPJ' in label:
                for i, cell in enumerate(row.get('cells', [])):
                    if i < len(col_map):
                        period = col_map[i]['period'].lower()
                        
                        tpj_per_kapal = pendapatan_jasa_cells[i].get('val', 0.0) if (pendapatan_jasa_cells and i < len(pendapatan_jasa_cells)) else 0.0
                        try:
                            tpj_per_kapal = float(tpj_per_kapal)
                        except (ValueError, TypeError):
                            tpj_per_kapal = 0.0
                            
                        tpj_semua = 0.0
                        if period in ['q1', 'q2', 'q3', 'q4']:
                            q_num = int(period[1])
                            if not tpj_semua_df.empty:
                                tpj_semua = tpj_semua_df[tpj_semua_df['quarter'] == q_num]['value'].sum()
                        else:
                            if not tpj_semua_df.empty:
                                tpj_semua = tpj_semua_df['value'].sum()
                                
                        val = 0.0
                        if tpj_semua != 0:
                            val = (tpj_per_kapal / tpj_semua)
                            
                        # Save to env_vars so it can be used in algebraic formulas like `tbab.sumq3_25 * prop_tpj`
                        env_vars[i]['prop_tpj'] = val
                        
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f} %".format(val * 100) if abs(val) >= 0.00005 else "-"
                        
            elif '% LABA (RUGI) BERSIH' in label.upper() or '% LABA' in label.upper():
                pendapatan_cells = total_pendapatan_jasa_cells if total_pendapatan_jasa_cells else pendapatan_jasa_cells
                
                for i, cell in enumerate(row.get('cells', [])):
                    if i < len(col_map):
                        laba = laba_rugi_bersih_cells[i].get('val', 0.0) if (laba_rugi_bersih_cells and i < len(laba_rugi_bersih_cells)) else 0.0
                        pendapatan = pendapatan_cells[i].get('val', 0.0) if (pendapatan_cells and i < len(pendapatan_cells)) else 0.0
                        
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
                        
        # 4. Evaluate Algebraic Formulas (multi-pass to resolve dependencies)
        for _ in range(3):
            for row in matrix.get('body', []):
                for i, cell in enumerate(row.get('cells', [])):
                    if i >= len(col_map):
                        continue
                        
                    val_c = str(cell.get('val_c', ''))
                    # Evaluate if it's an assignment like "var = expr" and not an Odoo domain list "['...']"
                    if '=' in val_c and '[' not in val_c and 'balp' not in val_c and 'tpj_skf' not in val_c and 'sumq1' not in val_c:
                        parts = val_c.split('=', 1)
                        if len(parts) == 2:
                            var_name = parts[0].split('.')[0].strip()
                            expr = parts[1].strip()
                            
                            try:
                                from collections import defaultdict
                                safe_env = defaultdict(float, env_vars[i])
                                safe_env.update(self.query_vars) # Inject MIS queries (e.g. tbab.sumq1_25)
                                val = eval(expr, {}, safe_env)
                                val = float(val)
                                
                                # Auto-proportional logic for Indirect Costs
                                label_upper = str(row.get('label', '')).upper()
                                is_expense = ('BIAYA' in label_upper or 'BEBAN' in label_upper or 'PENYUSUTAN' in label_upper)
                                
                                if is_expense and 'prop_tpj' not in expr:
                                    if any(q in expr for q in self.query_vars.keys()):
                                        val = val * safe_env.get('prop_tpj', 0.0)
                                        
                            except Exception:
                                val = 0.0
                                
                            # Format as percentage if it contains % or persentase
                            label_upper = str(row.get('label', '')).upper()
                            if '%' in label_upper or 'PERSENTASE' in label_upper:
                                cell['val'] = val
                                cell['val_r'] = "{:,.2f} %".format(val * 100) if abs(val) >= 0.00005 else "-"
                            else:
                                cell['val'] = val
                                cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"
                                
                            if var_name:
                                env_vars[i][var_name] = val
                            

        # 5. Final Pass: Clean up ALL zeroes across the entire matrix (including Odoo skeleton leftovers)
        for row in matrix.get('body', []):
            for cell in row.get('cells', []):
                val = cell.get('val')
                val_r = str(cell.get('val_r', '')).strip()
                
                # Check string representations first
                if val_r in ['0.00', '-0.00', '0', '-0', '0.00 %', '-0.00 %']:
                    cell['val_r'] = "-"
                    cell['val'] = 0.0
                elif val is not None and val != '':
                    try:
                        num_val = float(str(val).replace(',', ''))
                        if abs(num_val) < 0.005:
                            cell['val_r'] = "-"
                            cell['val'] = 0.0
                    except (ValueError, TypeError):
                        pass

        self.engine.close()

        return matrix
