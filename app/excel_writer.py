import os
import xlsxwriter
import re

class ExcelWriter:
    def __init__(self, output_path: str, matrix_data: dict, report_name: str, company_name: str, year: int):
        self.output_path = output_path
        self.matrix = matrix_data
        self.report_name = report_name
        self.company_name = company_name
        self.year = year
        
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
                # Convert em to roughly indent levels
                match = re.match(r'([0-9.]+)', v)
                if match:
                    try:
                        em_val = float(match.group(1))
                        # 1 em roughly 1 indent level
                        fmt['indent'] = int(em_val)
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
        title_format = workbook.add_format({'bold': True, 'font_size': 14})
        worksheet.write(0, 0, self.company_name, title_format)
        worksheet.write(1, 0, self.report_name, title_format)
        worksheet.write(2, 0, f"TAHUN {self.year}", title_format)
        
        start_row = 5
        
        # 1. Write Headers
        headers = self.matrix.get('header', [])
        current_row = start_row
        max_cols = 0
        
        # Header formatting
        for h_row in headers:
            col_idx = 1 # Start from column 1 (B) for data, column 0 (A) is for labels
            if current_row == start_row:
                # Top-left empty cell
                worksheet.write(current_row, 0, "Keterangan", self._get_format(workbook, {}, is_header=True))
                
            cols = h_row if isinstance(h_row, list) else h_row.get('cols', [])
            for c in cols:
                label = c.get('label', c.get('val', ''))
                colspan = c.get('colspan', 1)
                
                fmt = self._get_format(workbook, {}, is_header=True)
                if colspan > 1:
                    worksheet.merge_range(current_row, col_idx, current_row, col_idx + colspan - 1, label, fmt)
                else:
                    worksheet.write(current_row, col_idx, label, fmt)
                col_idx += colspan
                
            if col_idx - 1 > max_cols:
                max_cols = col_idx - 1
                
            current_row += 1
            
        # 2. Write Body (Data Rows)
        body = self.matrix.get('body', [])
        for row_data in body:
            row_style = self._parse_style(row_data.get('style', ''))
            label = row_data.get('label', '')
            
            # Write Label in Column A
            label_fmt = self._get_format(workbook, row_style)
            worksheet.write(current_row, 0, label, label_fmt)
            
            # Write Cells
            col_idx = 1
            cells = row_data.get('cells', [])
            
            # Pad cells if Odoo returned a ragged array (e.g. invalid columns)
            if len(cells) < max_cols:
                cells.extend([{'val': None}] * (max_cols - len(cells)))
                
            for c in cells:
                cell_style = self._parse_style(c.get('style', ''))
                # Merge row style with cell style
                merged_style = {**row_style, **cell_style}
                
                val = c.get('val')
                val_r = c.get('val_r', '')
                
                if str(val) == 'undefined' or str(val_r) == 'undefined' or str(val) == '#ERR' or str(val_r) == '#ERR':
                    val = None
                
                # Determine number format
                num_format = '#,##0.00'
                if '%' in str(val_r):
                    num_format = '0.00%'
                    # Odoo gives % as 0.75 for 75% or sometimes 75.0 for 75%. Let's trust the val for numeric operations
                
                cell_fmt = self._get_format(workbook, merged_style, num_format=num_format)
                
                if val is None or str(val) == '':
                    worksheet.write_string(current_row, col_idx, '', cell_fmt)
                elif isinstance(val, (int, float)):
                    worksheet.write_number(current_row, col_idx, val, cell_fmt)
                else:
                    worksheet.write_string(current_row, col_idx, str(val), cell_fmt)
                    
                col_idx += 1
                
            current_row += 1
            
        # 3. Adjust Column Widths
        worksheet.set_column(0, 0, 45) # Label column wide
        if col_idx > 1:
            worksheet.set_column(1, col_idx - 1, 15) # Data columns
            
        workbook.close()
        print(f"Report saved to {self.output_path}\n")
