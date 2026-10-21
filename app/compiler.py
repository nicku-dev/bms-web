import re
import pandas as pd
from app.engine import ReportEngine
from types import SimpleNamespace

from app.compiler_fetcher import CompilerFetcher
from app.compiler_evaluator import CompilerEvaluator

class FastMatrixCompiler:
    def __init__(self, db_name, year, report_type='fps', odoo_report_id=None, pg_kwargs=None, template_name=None):
        self.engine = ReportEngine(db_name, pg_kwargs=pg_kwargs)
        self.year = str(year)
        self.report_type = report_type
        self.odoo_report_id = odoo_report_id
        self.template_name = template_name or ''
        
        # 1. Isolate Fetcher
        self.fetcher = CompilerFetcher(self.engine, self.year, report_type)
        
        # 2. Fetch MIS Report Queries as Objects for eval()
        self.query_vars = {}
        if self.odoo_report_id:
            queries_data = self.engine.get_mis_report_queries(self.odoo_report_id)
            for q_name, q_fields in queries_data.items():
                if self.report_type == 'ho' or self.is_non_bms:
                    zero_fields = {k: 0.0 for k in q_fields}
                    self.query_vars[q_name] = SimpleNamespace(**zero_fields)
                else:
                    expanded_fields = dict(q_fields)
                    for k, v in q_fields.items():
                        if '_25' in k:
                            expanded_fields[k.replace('_25', '_26')] = v
                        elif '_26' in k:
                            expanded_fields[k.replace('_26', '_25')] = v
                        for q_num in ['1', '2', '3', '4']:
                            if f'sumq{q_num}' in k:
                                expanded_fields[f'sumq{q_num}'] = v
                                expanded_fields[f'q{q_num}'] = v
                        if 'ytd' in k:
                            expanded_fields['ytd'] = v
                    self.query_vars[q_name] = SimpleNamespace(**expanded_fields)
                
        # 3. Isolate Evaluator
        self.evaluator = CompilerEvaluator(self.query_vars)

    @property
    def is_non_bms(self) -> bool:
        name = (self.template_name or '').upper()
        rtype = (self.report_type or '').upper()
        if 'NON BMS' in name or 'NON-BMS' in name or 'NON_BMS' in name:
            return True
        if rtype in ['NON_BMS', 'NON-BMS', 'NON BMS']:
            return True
        return False

    def compile(self, matrix):
        print("🚀 FAST MATRIX COMPILER INITIATED")
        
        # 1. Map columns to vessel and quarter
        col_map = []
        if len(matrix.get('header', [])) >= 2:
            h0 = matrix['header'][0]
            h1 = matrix['header'][1]
            
            if isinstance(h0, dict): h0 = h0.get('cols', [])
            if isinstance(h1, dict): h1 = h1.get('cols', [])
            
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
        
        # Extract unique vessels present in the report (excluding TOTAL and Head Office)
        report_vessels = list(dict.fromkeys([
            col['vessel_name'].replace('Kapal - ', '').strip()
            for col in col_map 
            if col.get('vessel_name') and 'TOTAL' not in col['vessel_name'].upper() and 'HEAD OFFICE' not in col['vessel_name'].upper()
        ]))

        tpj_semua = self.engine.get_kpi_tpj_semua(self.year)
        tpj_terpilih = self.engine.get_kpi_tpj_kapal_terpilih(self.year, vessel_names=report_vessels)
        
        env_vars = [{} for _ in range(len(col_map))]

        # For HO and Non-BMS: Zero out indirect TPJ query rows (Warna Kuning: Angka di Line TPJ di 0 Kan)
        if self.report_type == 'ho' or self.is_non_bms:
            tpj_queries = ['tbg', 'tbp', 'tbk', 'tbj', 'tbak', 'tbpga', 'tpbb', 'tpll', 'tlsk', 'tbll', 'tbab', 'trsk', 'tbpll']
            for row in matrix.get('body', []):
                val_c_0 = str(row['cells'][0].get('val_c', '')) if row.get('cells') else ''
                if any(q in val_c_0 for q in tpj_queries):
                    for cell in row.get('cells', []):
                        cell['val'] = 0.0
                        cell['val_r'] = "-"

        # STEP 1 & 2: Process direct accounting queries and tag filters
        for row in matrix.get('body', []):
            label = str(row.get('label', '')).upper()
            
            tag_name = None
            account_code = None
            
            tag_match = re.search(r'#(.*?)#', label)
            if tag_match:
                tag_name = tag_match.group(1).replace('%', '')
                
            if label == 'PENDAPATAN JASA':
                tag_name = 'TW_PENDAPATAN JASA'
                
            if not tag_name:
                acc_match = re.search(r'^(\d+)', label)
                if acc_match:
                    account_code = acc_match.group(1).replace('%', '')

            # Also check if val_c contains an account_id.code or balp tag
            if not tag_name and not account_code and len(row.get('cells', [])) > 0:
                val_c = str(row['cells'][0].get('val_c', ''))
                if 'account_id.code' in val_c:
                    acc_match_c = re.search(r'\[\("account_id\.code","=","(.*?)"\)\]', val_c.replace("'", '"'))
                    if acc_match_c:
                        account_code = acc_match_c.group(1).replace('%', '')
                elif 'balp' in val_c:
                    tag_match_c = re.search(r'\[\("tag_ids\.name","=","(.*?)"\)\]', val_c.replace("'", '"'))
                    if tag_match_c:
                        tag_name = tag_match_c.group(1)

            query_code = str(row.get('query_code') or '').upper()
            val_c_first = str(row['cells'][0].get('val_c', '')) if row.get('cells') else ''

            if not tag_name and not account_code:
                if label in ['TRIP', 'TRIP KAPAL'] or query_code == 'TRIP' or 'kpi_trip' in val_c_first:
                    df = self.fetcher.get_kpi_trip()
                elif 'KAPASITAS' in label or query_code == 'KAPASITAS' or 'kpi_kapasitas' in val_c_first:
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
                        if self.report_type == 'ho' or clean_vessel.upper() in ['HO', 'HEAD OFFICE']:
                            vessel_df = df
                        else:
                            vessel_df = df[df['vessel_name'] == clean_vessel]
                            if vessel_df.empty:
                                vessel_df = df[df['vessel_name'].str.contains(clean_vessel, regex=False, na=False)]
                            if vessel_df.empty and 'ALL' in df['vessel_name'].values:
                                vessel_df = df[df['vessel_name'] == 'ALL']
                            
                        if not vessel_df.empty:
                            if period in ['q1', 'q2', 'q3', 'q4']:
                                q_num = int(period[1])
                                val = vessel_df[vessel_df['quarter'] == q_num]['value'].sum()
                                # Engine returns -balance; expense rows are shown as debit - credit.
                                if is_expense:
                                    val = -val
                            elif period == 'ytd' or period == 'total':
                                if 'KAPASITAS' in label or query_code == 'KAPASITAS' or 'kpi_kapasitas' in val_c_first:
                                    # Static metric: YTD must NOT be summed across quarters.
                                    # Odoo's own YTD value is unusable (0.0), so use the static ship capacity.
                                    val = vessel_df['value'].max()
                                else:
                                    # Strict YTD = Q1 + Q2 + Q3 + Q4 for each vessel
                                    q_indices = [
                                        j for j, c in enumerate(col_map)
                                        if c['period'] in ['q1', 'q2', 'q3', 'q4'] and c['vessel_name'] == vessel
                                    ]
                                    if q_indices:
                                        val = sum((row['cells'][j].get('val') or 0.0) for j in q_indices)
                                    else:
                                        val = vessel_df['value'].sum()
                                        if is_expense:
                                            val = -val
                                
                        try:
                            val = float(val)
                            # Sign is preserved: expense accounts may legitimately be negative
                            # (e.g. credits/insurance claims exceeding debits).
                        except (ValueError, TypeError):
                            val = 0.0
                            
                        cell['val'] = val
                        cell['raw_val'] = val
                        cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"

        # STEP 2.5: Calculate "Total Kapal Terpilih" base values by summing ship columns and copying val_c
        for row in matrix.get('body', []):
            if row.get('row_type') == 'title':
                for cell in row.get('cells', []):
                    cell['val'] = None
                    cell['val_r'] = ''
                continue

            cells = row.get('cells', [])
            if not cells: continue
            
            base_val_c = str(cells[0].get('val_c', ''))
            
            for i, col in enumerate(col_map):
                if i >= len(cells): continue
                
                # Copy val_c if missing or corrupted by Odoo Traceback (to ensure Step 4 evaluates formulas)
                if 'val_c' not in cells[i] or not cells[i]['val_c'] or 'Traceback' in str(cells[i].get('val_c', '')):
                    cells[i]['val_c'] = base_val_c

                if 'TOTAL' in col['vessel_name'].upper():
                    # Formula rows and percentage rows should be evaluated via formula in Step 4, not summed linearly
                    if row.get('row_type') == 'formula' or row.get('is_percentage'):
                        continue

                    period = col['period']
                    # Find all ship columns for this period
                    ship_cols = [j for j, c in enumerate(col_map) if c['period'] == period and 'TOTAL' not in c['vessel_name'].upper()]
                    
                    total_val = 0.0
                    for j in ship_cols:
                        v = cells[j].get('val', 0.0)
                        if v is not None:
                            total_val += v
                            
                    cells[i]['val'] = total_val
                    cells[i]['raw_val'] = total_val
                    cells[i]['val_r'] = "{:,.2f}".format(total_val) if abs(total_val) >= 0.005 else "-"

        # STEP 3: Store variables to env_vars for step 4
        # var_owner remembers which row first defined a variable (first occurrence wins),
        # so only that row may refresh the variable after its formula is evaluated in Step 4.
        var_owner = {}

        def _num(v):
            try:
                return 0.0 if v is None else float(v)
            except (ValueError, TypeError):
                return 0.0

        for row_idx, row in enumerate(matrix.get('body', [])):
            label = str(row.get('label', '')).upper()
            for i, cell in enumerate(row.get('cells', [])):
                if i >= len(col_map):
                    continue
                    
                val_c = str(cell.get('val_c', ''))
                if '=' in val_c:
                    parts = val_c.split('=', 1)
                    if len(parts) == 2:
                        var_name = parts[0].strip()
                        # Some names have prefixes (e.g. tpj.balp), strip them for env var name
                        var_name_clean = var_name.split('.')[0]
                        
                        # Only claim ownership if the RHS is not empty.
                        # Empty RHS means it's a parent text header that shouldn't shadow child data.
                        if parts[1].strip() != "":
                            if var_name_clean not in env_vars[i]:
                                env_vars[i][var_name_clean] = _num(cell.get('val', 0.0))
                                var_owner[(i, var_name_clean)] = row_idx
                            if var_name not in env_vars[i]:
                                env_vars[i][var_name] = _num(cell.get('val', 0.0))
                                var_owner[(i, var_name)] = row_idx

                # Also register row name and aliases if available
                row_name = str(row.get('name') or '').strip()
                if row_name:
                    if row_name not in env_vars[i] or not row.get('is_child'):
                        env_vars[i][row_name] = _num(cell.get('val', 0.0))
                
                query_code_r = str(row.get('query_code') or '').upper()
                if 'KAPASITAS' in label or query_code_r == 'KAPASITAS':
                    env_vars[i]['kapasitas'] = _num(cell.get('val', 0.0))
                elif label in ['TRIP', 'TRIP KAPAL'] or query_code_r == 'TRIP':
                    env_vars[i]['trip'] = _num(cell.get('val', 0.0))

                if label in ['PENDAPATAN JASA', 'TW_PENDAPATAN JASA']:
                    if cell.get('val') is not None and float(cell.get('val') or 0.0) != 0.0:
                        env_vars[i]['tpj'] = float(cell.get('val'))
                    elif 'tpj' not in env_vars[i]:
                        env_vars[i]['tpj'] = float(cell.get('val') or 0.0)

        # Fallback period sums from columns if get_kpi_tpj_semua is empty
        period_sums = {}
        for i, col in enumerate(col_map):
            if 'total' not in col['vessel_name'].lower():
                p = col['period']
                period_sums[p] = period_sums.get(p, 0.0) + float(env_vars[i].get('tpj') or 0.0)

        # Build tpj_semua and tpj_terpilih values to the environment
        for i, col in enumerate(col_map):
            period = col['period']
            if not tpj_semua.empty:
                if period in ['q1', 'q2', 'q3', 'q4']:
                    q_num = int(period[1])
                    val = tpj_semua[tpj_semua['quarter'] == q_num]['value'].sum()
                    env_vars[i]['tpj_semua'] = val
                elif period == 'ytd' or period == 'total':
                    env_vars[i]['tpj_semua'] = tpj_semua['value'].sum()
            else:
                env_vars[i]['tpj_semua'] = period_sums.get(period, 0.0)

            if not tpj_terpilih.empty:
                if period in ['q1', 'q2', 'q3', 'q4']:
                    q_num = int(period[1])
                    val_terpilih = tpj_terpilih[tpj_terpilih['quarter'] == q_num]['value'].sum()
                    env_vars[i]['tpj_terpilih'] = val_terpilih
                elif period == 'ytd' or period == 'total':
                    env_vars[i]['tpj_terpilih'] = tpj_terpilih['value'].sum()
            else:
                env_vars[i]['tpj_terpilih'] = period_sums.get(period, 0.0)
                
            tpj = float(env_vars[i].get('tpj') or 0.0)
            tpj_s = float(env_vars[i].get('tpj_semua') or 0.0)
            tpj_t = float(env_vars[i].get('tpj_terpilih') or 0.0)
            if self.report_type == 'ho' or self.is_non_bms:
                env_vars[i]['prop_tpj'] = 0.0
                env_vars[i]['ptpj'] = 0.0
            elif tpj_t != 0:
                env_vars[i]['prop_tpj'] = tpj / tpj_t
                env_vars[i]['ptpj'] = tpj / tpj_t
            elif tpj_s != 0:
                env_vars[i]['prop_tpj'] = tpj / tpj_s
                env_vars[i]['ptpj'] = tpj / tpj_s
            else:
                env_vars[i]['prop_tpj'] = 0.0
                env_vars[i]['ptpj'] = 0.0

            env_vars[i]['prop_tpj_terpilih'] = (tpj / tpj_t) if tpj_t != 0 else 0.0
            env_vars[i]['kpi_tpj_semua'] = env_vars[i]['tpj_semua']
            env_vars[i]['kpi_tpj_terpilih'] = env_vars[i]['tpj_terpilih']

        # Proporsional TPJ row insertion logic
        for row in matrix.get('body', []):
            label = str(row.get('label', '')).upper()
            query_code = str(row.get('query_code') or '').upper()
            row_name = str(row.get('name') or '').strip()
            if 'TPJ PER KAPAL' in label:
                if self.report_type == 'ho' or self.is_non_bms:
                    for cell in row.get('cells', []):
                        cell['val'] = 0.0
                        cell['val_r'] = "-"
                else:
                    for i, cell in enumerate(row.get('cells', [])):
                        if i < len(env_vars):
                            val = env_vars[i].get('tpj', 0.0)
                            cell['val'] = val
                            cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"
                            if row_name:
                                env_vars[i][row_name] = val
                                env_vars[i][row_name.lower()] = val
            elif 'TPJ SEMUA KAPAL' in label or query_code == 'TPJ_SEMUA':
                for i, cell in enumerate(row.get('cells', [])):
                    if i < len(env_vars):
                        val = 0.0 if (self.report_type == 'ho' or self.is_non_bms) else env_vars[i].get('tpj_semua', 0.0)
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"
                        if row_name:
                            env_vars[i][row_name] = val
                            env_vars[i][row_name.lower()] = val
            
            elif 'TPJ KAPAL TERPILIH' in label or 'TPJ TERPILIH' in label or query_code in ['TPJ_TERPILIH', 'TPJ_KAPAL_TERPILIH']:
                for i, cell in enumerate(row.get('cells', [])):
                    if i < len(env_vars):
                        val = 0.0 if (self.report_type == 'ho') else env_vars[i].get('tpj_terpilih', 0.0)
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"
                        if row_name:
                            env_vars[i][row_name] = val
                            env_vars[i][row_name.lower()] = val

            elif 'PROPORTIONAL TPJ' in label or 'PROPORSIONAL TPJ' in label:
                for i, cell in enumerate(row.get('cells', [])):
                    if i < len(env_vars):
                        val = 0.0 if (self.report_type == 'ho' or self.is_non_bms) else env_vars[i].get('prop_tpj', 0.0)
                        cell['val'] = val
                        cell['val_r'] = "{:,.2f} %".format(val * 100) if abs(val) >= 0.00005 else "-"
                        if row_name:
                            env_vars[i][row_name] = val
                            env_vars[i][row_name.lower()] = val

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

        # STEP 3.5
        for i in range(len(env_vars)):
            if env_vars[i].get("pendapatan") == 514981997.0:
                print(f"WOW! col {i} has pendapatan=514981997.0")
        # STEP 4: Evaluate Algebraic Formulas with ISOLATED Evaluator
        # Multiple passes so chained formulas (e.g. Langsung -> Operasional) settle.
        for _ in range(5):
            for row_idx, row in enumerate(matrix.get('body', [])):
                label_upper = str(row.get('label', '')).upper()
                
                # Prevent Odoo algebraic formulas from overwriting KPI data
                kpi_labels = ['KAPASITAS', 'KAPASITAS KAPAL', 'TRIP', 'TRIP KAPAL', 'TPJ PER KAPAL', 'TPJ SEMUA KAPAL', 'TPJ KAPAL TERPILIH', 'TPJ TERPILIH', 'PROPORTIONAL TPJ', 'PROPORSIONAL TPJ']
                if label_upper in kpi_labels or row.get('row_type') == 'query' or row.get('query_code'):
                    continue
                    
                is_expense = ('BIAYA' in label_upper or 'BEBAN' in label_upper or 'PENYUSUTAN' in label_upper)

                # Proportional Allocation for Auto TAG / Tag / Account rows
                if row.get('is_proportional') and row.get('multiplier_row'):
                    if self.report_type == 'ho':
                        # HO report retains raw full balances without vessel division
                        continue

                    mult_name = str(row.get('multiplier_row')).strip()
                    mult_clean = mult_name.lower()

                    # Check if multiplier row is formatted as percentage
                    mult_is_pct = False
                    for r_check in matrix.get('body', []):
                        r_name = str(r_check.get('name') or r_check.get('code') or '').strip().lower()
                        if r_name == mult_clean:
                            if r_check.get('is_percentage') or r_check.get('format') == 'percentage' or '%' in str(r_check.get('label', '')):
                                mult_is_pct = True
                            break

                    ship_totals = {}
                    # Calculate allocated values for each individual ship column
                    for i, cell in enumerate(row.get('cells', [])):
                        if i >= len(col_map):
                            continue
                        vessel = col_map[i]['vessel_name']
                        period = col_map[i]['period']

                        if 'total' in vessel.lower():
                            continue

                        if period in ['q1', 'q2', 'q3', 'q4']:
                            mult_val = env_vars[i].get(mult_clean, 0.0)
                            if mult_val == 0.0 and mult_clean in ['ptpj', 'prop_tpj', 'prop_tpj_terpilih']:
                                mult_val = env_vars[i].get('prop_tpj', 0.0) or env_vars[i].get('ptpj', 0.0)

                            if abs(mult_val) > 1.0 and (mult_is_pct or 'prop' in mult_clean or 'persen' in mult_clean):
                                factor = mult_val / 100.0
                            else:
                                factor = mult_val

                            raw_val = cell.get('raw_val')
                            if raw_val is None:
                                raw_val = cell.get('val', 0.0) or 0.0
                                cell['raw_val'] = raw_val

                            allocated = float(raw_val) * float(factor)
                            cell['val'] = allocated
                            cell['val_r'] = "{:,.2f}".format(allocated) if abs(allocated) >= 0.005 else "-"

                            ship_totals[period] = ship_totals.get(period, 0.0) + allocated

                            row_name = str(row.get('name') or '').strip()
                            if row_name:
                                env_vars[i][row_name] = allocated
                                env_vars[i][row_name.lower()] = allocated

                    # Calculate YTD for each individual vessel
                    for i, cell in enumerate(row.get('cells', [])):
                        if i >= len(col_map):
                            continue
                        vessel = col_map[i]['vessel_name']
                        period = col_map[i]['period']
                        if 'total' not in vessel.lower() and period in ['ytd', 'total']:
                            q_cols = [j for j, col in enumerate(col_map) if col['period'] in ['q1', 'q2', 'q3', 'q4'] and col['vessel_name'] == vessel]
                            ytd_val = sum((row['cells'][j].get('val') or 0.0) for j in q_cols)
                            cell['val'] = ytd_val
                            cell['val_r'] = "{:,.2f}".format(ytd_val) if abs(ytd_val) >= 0.005 else "-"
                            row_name = str(row.get('name') or '').strip()
                            if row_name:
                                env_vars[i][row_name] = ytd_val
                                env_vars[i][row_name.lower()] = ytd_val

                    # Calculate Total Kapal Terpilih columns
                    for i, cell in enumerate(row.get('cells', [])):
                        if i >= len(col_map):
                            continue
                        vessel = col_map[i]['vessel_name']
                        period = col_map[i]['period']
                        if 'total' in vessel.lower():
                            if period in ['q1', 'q2', 'q3', 'q4']:
                                tot = ship_totals.get(period, 0.0)
                                cell['val'] = tot
                                cell['val_r'] = "{:,.2f}".format(tot) if abs(tot) >= 0.005 else "-"
                            elif period in ['ytd', 'total']:
                                tot_ytd = sum(ship_totals.values())
                                cell['val'] = tot_ytd
                                cell['val_r'] = "{:,.2f}".format(tot_ytd) if abs(tot_ytd) >= 0.005 else "-"
                            row_name = str(row.get('name') or '').strip()
                            if row_name:
                                env_vars[i][row_name] = cell['val']
                                env_vars[i][row_name.lower()] = cell['val']
                    continue
                
                for i, cell in enumerate(row.get('cells', [])):
                    if i >= len(col_map):
                        continue
                        
                    val_c = str(cell.get('val_c', '')).replace('\xa0', ' ')
                    
                    # Evaluate if it's an assignment like "var = expr" and not an Odoo domain list "['...']"
                    if '=' in val_c and '[' not in val_c and 'balp' not in val_c and 'tpj_skf' not in val_c and 'sumq' not in val_c.split('=', 1)[0]:
                        parts = val_c.split('=', 1)
                        if len(parts) == 2:
                            expr = parts[1].strip()
                            
                            # Subperiod formulas like "var = q1 = expr1, q2 = expr2, ..."
                            period = col_map[i]['period']
                            sub_match = re.search(rf'\b{period}\s*=\s*([^,\n]+)', expr)
                            if sub_match:
                                expr = sub_match.group(1).strip()
                            elif period in ['q2', 'q3', 'q4']:
                                # If template formula only specified q1 (e.g. tbg.sumq1_26*ptpj.q1), adapt to current quarter
                                expr = re.sub(r'sumq1_', f'sum{period}_', expr)
                                expr = re.sub(r'sumq1\b', f'sum{period}', expr)
                                expr = re.sub(r'\.q1\b', f'.{period}', expr)
                            
                            if not expr:
                                cell['val'] = 0.0
                                cell['val_r'] = ""
                                continue
                                
                            try:
                                if (self.report_type == 'ho' or self.is_non_bms) and 'ptpj' in expr:
                                    val = 0.0
                                # YTD Override for indirect costs: sum Q1..Q4 instead of formula
                                elif col_map[i]['period'] in ['ytd', 'total'] and 'ptpj' in expr:
                                    vessel_name = col_map[i]['vessel_name']
                                    q_cols = [j for j, col in enumerate(col_map) if col['period'] in ['q1', 'q2', 'q3', 'q4'] and col['vessel_name'] == vessel_name]
                                    if q_cols:
                                        val = sum((row['cells'][j].get('val') or 0.0) for j in q_cols)
                                    else:
                                        val = self.evaluator.evaluate_algebraic(expr, env_vars[i], is_expense)
                                else:
                                    # USE THE ISOLATED EVALUATOR
                                    val = self.evaluator.evaluate_algebraic(expr, env_vars[i], is_expense)
                            except ValueError:
                                # DO NOT overwrite if evaluation fails cleanly!
                                continue
                                
                            # Feed the evaluated result back so dependent formulas see real values
                            # (only the row that owns the variable; children never overwrite parents).
                            var_name = parts[0].strip()
                            var_name_clean = var_name.split('.')[0]
                            if var_owner.get((i, var_name_clean)) == row_idx:
                                env_vars[i][var_name_clean] = val
                            if var_owner.get((i, var_name)) == row_idx:
                                env_vars[i][var_name] = val

                            # Format as percentage if is_percentage flag is set or label begins/ends with %
                            is_pct = bool(
                                row.get('is_percentage') or 
                                row.get('format') == 'percentage' or 
                                label_upper.strip().startswith('%') or 
                                label_upper.strip().endswith('%') or
                                'PERSEN' in label_upper
                            )
                            if is_pct:
                                cell['val'] = val
                                # Smart scaling: if already multiplied by 100 or scale is already in percentages (> 1.0)
                                expr_str = str(cell.get('val_c', '')).lower()
                                if '* 100' in expr_str or '*100' in expr_str or abs(val) > 1.0:
                                    pct_val = val
                                else:
                                    pct_val = val * 100
                                cell['val_r'] = "{:,.2f} %".format(pct_val) if abs(val) >= 0.00005 else ("0.00 %" if val == 0 else "-")
                            else:
                                cell['val'] = val
                                cell['val_r'] = "{:,.2f}".format(val) if abs(val) >= 0.005 else "-"
                                
        # STEP 5: Title Row & Error Cleanup
        # Blank out cells for rows that are purely titles (no formula, no account code),
        # replace #NAME or error artifacts with blank, and blank out TRIP/Rupiah per Trip for HO or when uncalculated.
        for row in matrix.get('body', []):
            cells = row.get('cells', [])
            if not cells:
                continue
                
            label = str(row.get('label', ''))
            label_upper = label.upper()
            
            c0 = cells[0]
            val_c = str(c0.get('val_c', ''))
            
            is_empty_assignment = False
            if val_c and '=' in val_c:
                parts = val_c.split('=', 1)
                if len(parts) == 2 and not parts[1].strip():
                    is_empty_assignment = True
                    
            if not val_c or is_empty_assignment:
                has_account_code = len(label.split()) > 0 and label.split()[0].isdigit() and len(label.split()[0]) >= 6
                
                if not has_account_code:
                    for c in cells:
                        c['val'] = ''
                        c['val_r'] = ''
                        
            # Clean TRIP and Rupiah per Trip (replace #NAME with blank)
            if any(k in label_upper for k in ['TRIP', 'RUPIAH PER TRIP']):
                for c in cells:
                    vr = str(c.get('val_r', ''))
                    v = str(c.get('val', ''))
                    if self.report_type == 'ho' or '#NAME' in vr or '#NAME' in v or c.get('val') is None:
                        c['val'] = ''
                        c['val_r'] = ''

            # General #NAME cleanup for all rows
            for c in cells:
                if '#NAME' in str(c.get('val_r', '')) or '#NAME' in str(c.get('val', '')):
                    c['val'] = ''
                    c['val_r'] = ''
                        
        # Filter out hidden rows for Kapal Non BMS (TPJ Per Kapal, TPJ Semua Kapal, Proportional TPJ)
        if self.is_non_bms:
            hidden_labels = [
                'TPJ PER KAPAL',
                'TPJ SEMUA KAPAL',
                'PROPORTIONAL TPJ',
                'PROPORSIONAL TPJ'
            ]
            matrix['body'] = [
                row for row in matrix.get('body', [])
                if not any(hl in str(row.get('label', '')).upper() for hl in hidden_labels)
            ]

        return matrix
