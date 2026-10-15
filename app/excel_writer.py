import os
import xlsxwriter
import re

class ExcelWriter:
    def __init__(self, output_path: str, matrix_data: dict, report_name: str, company_name: str, year: int, db_name: str = "", compile_status: str = ""):
        self.output_path = output_path
        self.matrix = matrix_data
        self.report_name = report_name
        self.company_name = company_name
        self.year = year
        self.db_name = db_name
        self.compile_status = compile_status
        
        # Cache for xlsxwriter formats so we don't exceed limits
        self._format_cache = {}

    def _parse_style(self, style_str: str) -> dict:
        """Parses CSS-like style string from Odoo to xlsxwriter format dict."""
        fmt = {}
        if not style_str:
            return fmt
            
        styles = [s.strip() for s in style_str.split(';') if s.strip()]
        for s in styles:
            if ':' not in s:
                continue
            k, v = [x.strip() for x in s.split(':', 1)]
            
            if k == 'font-weight' and v == 'bold':
                fmt['bold'] = True
            elif k == 'font-style' and v == 'italic':
                fmt['italic'] = True
            elif k == 'color':
                fmt['font_color'] = v
            elif k == 'background-color':
                fmt['bg_color'] = v
            elif k == 'text-indent':
                match = re.match(r'([0-9.]+)', v)
                if match:
                    try:
                        em_val = float(match.group(1))
                        if em_val >= 4:
                            fmt['indent'] = 2
                        elif em_val >= 2:
                            fmt['indent'] = 1
                        else:
                            fmt['indent'] = 0
                    except:
                        pass
        return fmt

    def _get_format(self, workbook, style_dict, is_header=False, num_format=None):
        """Returns an xlsxwriter format object based on dict, utilizing caching."""
        # Create a cache key based on the dict properties
        key_items = list(style_dict.items())
        key_items.sort()
        key_tuple = tuple(key_items) + (is_header, num_format)
        
        if key_tuple in self._format_cache:
            return self._format_cache[key_tuple]
            
        fmt_dict = dict(style_dict)
        if is_header:
            fmt_dict['bold'] = True
            fmt_dict['align'] = 'center'
            fmt_dict['valign'] = 'vcenter'
            fmt_dict['border'] = 1
        else:
            fmt_dict['border'] = 1
            
        if num_format:
            fmt_dict['num_format'] = num_format
            
        fmt = workbook.add_format(fmt_dict)
        self._format_cache[key_tuple] = fmt
        return fmt

    def generate(self):
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        workbook = xlsxwriter.Workbook(self.output_path)
        worksheet = workbook.add_worksheet('Report')
        
        # Write Report Titles
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'font_name': 'Calibri'})
        subtitle_format = workbook.add_format({'bold': True, 'font_size': 12, 'font_name': 'Calibri', 'font_color': '#334155'})
        year_format = workbook.add_format({'bold': True, 'font_size': 11, 'font_name': 'Calibri', 'font_color': '#475569'})
        
        worksheet.write(0, 0, self.company_name, title_format)
        worksheet.write(1, 0, self.report_name, subtitle_format)
        worksheet.write(2, 0, f"TAHUN {self.year}", year_format)
        
        start_row = 5
        
        # 1. Write Headers
        headers = self.matrix.get('header', [])
        num_header_rows = len(headers)
        current_row = start_row
        max_cols = 0
        
        header_fmt = self._get_format(workbook, {'bg_color': '#EAEEF3', 'font_color': '#0F172A'}, is_header=True)
        
        # Merge top-left "Keterangan" vertically across all header rows
        if num_header_rows > 1:
            worksheet.merge_range(start_row, 0, start_row + num_header_rows - 1, 0, "Keterangan", header_fmt)
        else:
            worksheet.write(start_row, 0, "Keterangan", header_fmt)
            
        for h_row in headers:
            col_idx = 1 # Start from column 1 (B) for data, column 0 (A) is for labels
            cols = h_row if isinstance(h_row, list) else h_row.get('cols', [])
            for c in cols:
                label = c.get('label', c.get('val', ''))
                colspan = c.get('colspan', 1)
                
                if colspan > 1:
                    worksheet.merge_range(current_row, col_idx, current_row, col_idx + colspan - 1, label, header_fmt)
                else:
                    worksheet.write(current_row, col_idx, label, header_fmt)
                col_idx += colspan
                
            if col_idx - 1 > max_cols:
                max_cols = col_idx - 1
                
            current_row += 1
            
        # 2. Write Body (Data Rows)
        standard_num_format = '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'
        percent_num_format = '0.00%'
        
        body = self.matrix.get('body', [])
        for row_data in body:
            raw_style = row_data.get('style', '')
            row_style = self._parse_style(raw_style)
            label = str(row_data.get('label', ''))
            trimmed_label = label.strip()
            
            cells = row_data.get('cells', [])
            # Pad cells if Odoo returned a ragged array
            if len(cells) < max_cols:
                cells.extend([{'val': None}] * (max_cols - len(cells)))
                
            # Classify row type:
            # A. Detail COA: starts with 6-10 digit account code (e.g. 5000032400)
            is_coa_detail = bool(re.match(r'^\d{6,10}\s', trimmed_label))
            
            # C. Total row (e.g. Total Biaya Tetap)
            is_total_row = 'Total' in label or 'Laba' in label or 'Rugi' in label or 'bg_color' in row_style
            
            # B. Section Heading: bold, no account code, no em indent, not total, and all cells are truly empty strings
            is_empty_cells = all(
                c is None or c.get('val') is None or str(c.get('val', '')).strip() in ['', 'None', 'undefined']
                for c in cells
            )
            is_section_heading = (
                row_style.get('bold', False)
                and not is_coa_detail
                and not is_total_row
                and ('text-indent' not in raw_style or row_style.get('indent', 0) == 0)
                and is_empty_cells
            )
            
            # Apply specialized visual styling
            if is_section_heading:
                row_style['bold'] = True
                row_style['bg_color'] = row_style.get('bg_color', '#F1F5F9')
                row_style['font_color'] = '#0F172A'
                row_style['indent'] = 0
            elif is_coa_detail:
                row_style['bold'] = False
                row_style['italic'] = True
                row_style['font_color'] = '#555555'
                row_style['indent'] = max(row_style.get('indent', 2), 2)
            elif is_total_row and 'bg_color' in row_style:
                row_style['bold'] = True
                
            # Write Label in Column A
            label_fmt = self._get_format(workbook, row_style)
            worksheet.write(current_row, 0, label, label_fmt)
            
            # Write Cells
            col_idx = 1
            for c in cells:
                cell_style = self._parse_style(c.get('style', ''))
                merged_style = {**row_style, **cell_style}
                
                # For Detail COA, make numbers italic & muted gray to match label
                if is_coa_detail:
                    merged_style['italic'] = True
                    merged_style['bold'] = False
                    merged_style['font_color'] = '#555555'
                    
                val = c.get('val')
                val_r = c.get('val_r', '')
                
                if str(val) == 'undefined' or str(val_r) == 'undefined' or '#ERR' in str(val) or '#ERR' in str(val_r) or '#NAME' in str(val) or '#NAME' in str(val_r):
                    val = None
                    val_r = ''
                
                # Determine number format
                num_format = standard_num_format
                if '%' in str(val_r):
                    num_format = percent_num_format
                
                cell_fmt = self._get_format(workbook, merged_style, num_format=num_format)
                
                if is_section_heading or val is None or str(val).strip() == '':
                    worksheet.write_string(current_row, col_idx, '', cell_fmt)
                else:
                    try:
                        cleaned_val = str(val).replace(',', '')
                        numeric_val = float(cleaned_val)
                        if abs(numeric_val) < 0.005:
                            numeric_val = 0.0
                        worksheet.write_number(current_row, col_idx, numeric_val, cell_fmt)
                    except (ValueError, TypeError):
                        worksheet.write_string(current_row, col_idx, str(val), cell_fmt)
                    
                col_idx += 1
                
            current_row += 1
            
        # 3. Adjust Column Widths
        worksheet.set_column(0, 0, 45) # Label column wide
        if col_idx > 1:
            worksheet.set_column(1, col_idx - 1, 15) # Data columns
            
        # 4. Add Log Sistem Sheet
        log_sheet = workbook.add_worksheet('Log Sistem')
        log_sheet.set_column(0, 0, 25)
        log_sheet.set_column(1, 1, 60)
        
        bold_fmt = workbook.add_format({'bold': True})
        
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_sheet.write(0, 0, "Log Information", title_format)
        
        log_sheet.write(2, 0, "Waktu Penarikan Data", bold_fmt)
        log_sheet.write(2, 1, now_str)
        
        log_sheet.write(3, 0, "Database Odoo Sumber", bold_fmt)
        log_sheet.write(3, 1, self.db_name)
        
        log_sheet.write(4, 0, "Status Sinkronisasi", bold_fmt)
        log_sheet.write(4, 1, self.compile_status)
            
        workbook.close()
        print(f"Report saved to {self.output_path}\n")
