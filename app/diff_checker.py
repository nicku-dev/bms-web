import io
import re
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from typing import Dict, List, Any, Optional, Tuple

def clean_vessel_name(name: str) -> str:
    """Normalizes vessel names across Odoo MIS Builder and BMS Web."""
    if not name:
        return ""
    n = str(name).strip()
    # Strip prefix 'Kapal - ' or 'KAPAL - '
    if n.upper().startswith("KAPAL - "):
        n = n[8:].strip()
    elif n.upper().startswith("KAPAL -"):
        n = n[7:].strip()
    elif n.upper().startswith("KAPAL-"):
        n = n[6:].strip()
        
    # Normalize multiple whitespaces
    n = re.sub(r'\s+', ' ', n)
    return n

def clean_row_label(label: str) -> str:
    """Normalizes row label for robust matching."""
    if not label:
        return ""
    l = str(label).strip()
    l = re.sub(r'\s+', ' ', l)
    return l

def parse_mis_builder_excel(file_bytes: bytes) -> Dict[str, Any]:
    """
    Parses Odoo MIS Builder standard Excel export.
    Returns:
    - metadata: company_name, report_title, report_subtitle, year
    - columns: list of { vessel, raw_vessel, period, col_idx }
    - rows: list of { row_idx, label, clean_label, cells: [float/None] }
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    
    # Metadata from header rows
    company_name = str(ws.cell(1, 1).value or "").strip()
    report_title = str(ws.cell(2, 1).value or "").strip()
    report_subtitle = str(ws.cell(3, 1).value or "").strip()
    year_val = str(ws.cell(4, 1).value or "").strip()
    
    # Header rows: Row 6 (Vessel) & Row 7 (Quarter/Period)
    # Col 1 is 'Keterangan'
    columns = []
    current_raw_vessel = None
    
    max_col = ws.max_column
    for c in range(2, max_col + 1):
        v_cell = ws.cell(6, c).value
        p_cell = ws.cell(7, c).value
        
        if v_cell is not None and str(v_cell).strip():
            current_raw_vessel = str(v_cell).strip()
            
        period = str(p_cell or "").strip().upper()
        if not period and current_raw_vessel is None:
            # Reached end of table columns
            continue
            
        columns.append({
            "col_idx": c,
            "raw_vessel": current_raw_vessel or "",
            "vessel": clean_vessel_name(current_raw_vessel or ""),
            "period": period
        })
        
    # Data rows: Row 8 onwards
    rows = []
    for r in range(8, ws.max_row + 1):
        lbl = ws.cell(r, 1).value
        if lbl is None or not str(lbl).strip():
            continue
            
        label = str(lbl).strip()
        cell_values = []
        has_any_num = False
        
        for col_info in columns:
            val = ws.cell(r, col_info["col_idx"]).value
            # Parse number
            if val is None or val == "" or val == "-":
                cell_values.append(0.0)
            else:
                try:
                    num_val = float(val)
                    cell_values.append(num_val)
                    if num_val != 0.0:
                        has_any_num = True
                except (ValueError, TypeError):
                    cell_values.append(0.0)
                    
        rows.append({
            "row_idx": r,
            "label": label,
            "clean_label": clean_row_label(label),
            "cells": cell_values,
            "has_data": has_any_num
        })
        
    return {
        "company_name": company_name,
        "report_title": report_title,
        "report_subtitle": report_subtitle,
        "year": year_val,
        "columns": columns,
        "rows": rows
    }


def compare_matrices(bms_matrix: Dict[str, Any], mis_data: Dict[str, Any], tolerance: float = 1.0) -> Dict[str, Any]:
    """
    Compares BMS Web matrix (live compilation) against parsed MIS Builder Excel data.
    Tolerance: absolute difference >= tolerance is considered a mismatch.
    """
    # 1. Map BMS Columns from matrix['header']
    bms_headers = bms_matrix.get("header", [])
    bms_cols = []
    if len(bms_headers) >= 2:
        h0 = bms_headers[0]
        h1 = bms_headers[1]
        if isinstance(h0, dict): h0 = h0.get("cols", [])
        if isinstance(h1, dict): h1 = h1.get("cols", [])
        
        vessels_expanded = []
        for h in h0:
            colspan = h.get("colspan", 1)
            raw_v = str(h.get("label", h.get("val", ""))).strip()
            vessels_expanded.extend([raw_v] * colspan)
            
        for i, h in enumerate(h1):
            raw_v = vessels_expanded[i] if i < len(vessels_expanded) else ""
            p = str(h.get("label", h.get("val", ""))).strip().upper()
            bms_cols.append({
                "idx": i,
                "raw_vessel": raw_v,
                "vessel": clean_vessel_name(raw_v),
                "period": p
            })
            
    # 2. Map MIS Columns
    mis_cols = mis_data.get("columns", [])
    
    # 3. Intersect / Align Columns
    mis_col_map = {(c["vessel"].upper(), c["period"].upper()): i for i, c in enumerate(mis_cols)}
    
    # Use BMS column ordering as primary
    aligned_columns = []
    for b_col in bms_cols:
        key = (b_col["vessel"].upper(), b_col["period"].upper())
        mis_idx = mis_col_map.get(key)
        aligned_columns.append({
            "vessel": b_col["vessel"],
            "raw_bms_vessel": b_col["raw_vessel"],
            "period": b_col["period"],
            "bms_col_idx": b_col["idx"],
            "mis_col_idx": mis_idx
        })

    # Group aligned columns by vessel for table header rendering
    vessel_headers = []
    current_vessel = None
    current_span = 0
    for col in aligned_columns:
        v_name = col["vessel"]
        if v_name != current_vessel:
            if current_vessel is not None:
                vessel_headers.append({"name": current_vessel, "colspan": current_span})
            current_vessel = v_name
            current_span = 1
        else:
            current_span += 1
    if current_vessel is not None:
        vessel_headers.append({"name": current_vessel, "colspan": current_span})

    # 4. Map MIS Rows by clean_label
    mis_row_map = {r["clean_label"].upper(): r for r in mis_data.get("rows", [])}
    
    # 5. Compare Row by Row
    bms_rows = bms_matrix.get("body", [])
    compared_rows = []
    
    total_cells = 0
    match_cells = 0
    mismatch_cells = 0
    mismatched_rows_count = 0
    discrepancy_list = []
    
    for r_idx, b_row in enumerate(bms_rows):
        label = b_row.get("label", "")
        code = b_row.get("code", "")
        clean_lbl = clean_row_label(label)
        
        # Try matching MIS row by clean_label or case-insensitive
        mis_r = mis_row_map.get(clean_lbl.upper())
        
        # If not exact match, try partial match (e.g., if code is embedded in MIS label)
        if not mis_r and code:
            for m_lbl, m_item in mis_row_map.items():
                if code.upper() in m_lbl:
                    mis_r = m_item
                    break

        b_cells = b_row.get("cells", [])
        compared_cells = []
        row_has_mismatch = False
        row_match_cnt = 0
        row_mismatch_cnt = 0
        
        for col_info in aligned_columns:
            b_idx = col_info["bms_col_idx"]
            m_idx = col_info["mis_col_idx"]
            
            # BMS Value
            b_val = 0.0
            if b_idx < len(b_cells):
                cell_obj = b_cells[b_idx]
                val_raw = cell_obj.get("val")
                if val_raw is not None and val_raw != "":
                    try:
                        b_val = float(val_raw)
                    except (ValueError, TypeError):
                        b_val = 0.0
            
            # MIS Value
            m_val = 0.0
            has_mis_val = False
            if mis_r and m_idx is not None and m_idx < len(mis_r["cells"]):
                m_val = float(mis_r["cells"][m_idx])
                has_mis_val = True
                
            diff = b_val - m_val
            abs_diff = abs(diff)
            is_match = abs_diff < tolerance
            
            total_cells += 1
            if is_match:
                match_cells += 1
                row_match_cnt += 1
            else:
                mismatch_cells += 1
                row_mismatch_cnt += 1
                row_has_mismatch = True
                
                # Add to discrepancy list for fast auditing
                discrepancy_list.append({
                    "row_code": code,
                    "row_label": label,
                    "vessel": col_info["vessel"],
                    "period": col_info["period"],
                    "bms_val": b_val,
                    "mis_val": m_val,
                    "diff": diff,
                    "abs_diff": abs_diff
                })
                
            compared_cells.append({
                "vessel": col_info["vessel"],
                "period": col_info["period"],
                "bms_val": b_val,
                "mis_val": m_val if has_mis_val else None,
                "diff": diff,
                "is_match": is_match,
                "has_mis": has_mis_val
            })
            
        if row_has_mismatch:
            mismatched_rows_count += 1
            
        compared_rows.append({
            "row_idx": r_idx,
            "code": code,
            "label": label,
            "has_mismatch": row_has_mismatch,
            "match_count": row_match_cnt,
            "mismatch_count": row_mismatch_cnt,
            "cells": compared_cells
        })
        
    accuracy_pct = round((match_cells / total_cells * 100), 2) if total_cells > 0 else 0.0
    
    return {
        "kpi": {
            "total_cells": total_cells,
            "match_cells": match_cells,
            "mismatch_cells": mismatch_cells,
            "accuracy_pct": accuracy_pct,
            "total_rows": len(compared_rows),
            "mismatched_rows_count": mismatched_rows_count
        },
        "headers": {
            "vessels": vessel_headers,
            "periods": [col["period"] for col in aligned_columns]
        },
        "columns": aligned_columns,
        "rows": compared_rows,
        "discrepancies": discrepancy_list[:500]  # top 500 discrepancies
    }


def export_diff_matrix_excel(diff_data: Dict[str, Any], company_name: str, report_name: str, year: int) -> bytes:
    """
    Generates an Excel workbook containing:
    1. 'Matriks Rekonsiliasi' (Diff Matrix with color highlighting: green for match, red for mismatch)
    2. 'Daftar Baris Selisih' (Audit table listing only rows & columns that differ)
    """
    wb = openpyxl.Workbook()
    # Default sheet
    ws_matrix = wb.active
    ws_matrix.title = "Matriks Rekonsiliasi"
    
    # Styles
    font_title = Font(name="Calibri", size=14, bold=True, color="1E293B")
    font_sub = Font(name="Calibri", size=11, bold=True, color="475569")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_normal = Font(name="Calibri", size=10)
    
    fill_header_navy = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_header_blue = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    fill_match = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")     # Light green
    fill_mismatch = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")  # Light red
    
    font_mismatch = Font(name="Calibri", size=10, bold=True, color="991B1B")
    font_match = Font(name="Calibri", size=10, color="166534")
    
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    # 1. Header Information in Sheet 1
    ws_matrix.cell(1, 1, f"{company_name} - LAPORAN REKONSILIASI").font = font_title
    ws_matrix.cell(2, 1, f"Template: {report_name} | Tahun: {year}").font = font_sub
    kpi = diff_data.get("kpi", {})
    ws_matrix.cell(3, 1, f"Akurasi: {kpi.get('accuracy_pct')}% | Total Sel: {kpi.get('total_cells'):,} | Cocok: {kpi.get('match_cells'):,} | Selisih: {kpi.get('mismatch_cells'):,}").font = font_bold
    
    headers = diff_data.get("headers", {})
    vessels = headers.get("vessels", [])
    periods = headers.get("periods", [])
    
    # Row 5: Vessel Header
    ws_matrix.cell(5, 1, "Keterangan Akun / Baris").font = font_header
    ws_matrix.cell(5, 1).fill = fill_header_navy
    ws_matrix.cell(5, 1).alignment = align_center
    ws_matrix.cell(5, 1).border = thin_border
    
    col_start = 2
    for v in vessels:
        span = v.get("colspan", 1)
        ws_matrix.cell(5, col_start, v.get("name")).font = font_header
        ws_matrix.cell(5, col_start).fill = fill_header_navy
        ws_matrix.cell(5, col_start).alignment = align_center
        ws_matrix.cell(5, col_start).border = thin_border
        
        if span > 1:
            ws_matrix.merge_cells(start_row=5, start_column=col_start, end_row=5, end_column=col_start + span - 1)
            for c in range(col_start, col_start + span):
                ws_matrix.cell(5, c).border = thin_border
        col_start += span
        
    # Row 6: Period Header
    ws_matrix.cell(6, 1, "").font = font_header
    ws_matrix.cell(6, 1).fill = fill_header_blue
    ws_matrix.cell(6, 1).border = thin_border
    
    for i, p in enumerate(periods):
        col_num = i + 2
        cell = ws_matrix.cell(6, col_num, p)
        cell.font = font_header
        cell.fill = fill_header_blue
        cell.alignment = align_center
        cell.border = thin_border
        
    # Data Rows
    current_row = 7
    for r in diff_data.get("rows", []):
        lbl_cell = ws_matrix.cell(current_row, 1, r.get("label", ""))
        lbl_cell.font = font_bold if r.get("has_mismatch") else font_normal
        lbl_cell.alignment = align_left
        lbl_cell.border = thin_border
        
        for i, c in enumerate(r.get("cells", [])):
            col_num = i + 2
            cell = ws_matrix.cell(current_row, col_num)
            
            diff_val = c.get("diff", 0.0)
            is_match = c.get("is_match", True)
            
            cell.value = diff_val
            cell.number_format = '#,##0.00;(#,##0.00);"-"'
            cell.alignment = align_right
            cell.border = thin_border
            
            if is_match:
                cell.fill = fill_match
                cell.font = font_match
            else:
                cell.fill = fill_mismatch
                cell.font = font_mismatch
                
        current_row += 1
        
    ws_matrix.column_dimensions['A'].width = 45
    for i in range(2, len(periods) + 2):
        col_letter = openpyxl.utils.get_column_letter(i)
        ws_matrix.column_dimensions[col_letter].width = 16

    # 2. Sheet 2: Discrepancy List (Daftar Baris Selisih)
    ws_disc = wb.create_sheet(title="Daftar Baris Selisih")
    disc_headers = ["No", "Kode", "Keterangan Baris", "Kapal / Armada", "Periode", "Nilai MIS Builder", "Nilai BMS Web", "Selisih (BMS - MIS)"]
    
    for c_idx, h_text in enumerate(disc_headers, 1):
        cell = ws_disc.cell(1, c_idx, h_text)
        cell.font = font_header
        cell.fill = fill_header_navy
        cell.alignment = align_center
        cell.border = thin_border
        
    d_row = 2
    for item in diff_data.get("discrepancies", []):
        ws_disc.cell(d_row, 1, d_row - 1).alignment = align_center
        ws_disc.cell(d_row, 2, item.get("row_code", "")).alignment = align_left
        ws_disc.cell(d_row, 3, item.get("row_label", "")).alignment = align_left
        ws_disc.cell(d_row, 4, item.get("vessel", "")).alignment = align_left
        ws_disc.cell(d_row, 5, item.get("period", "")).alignment = align_center
        
        c_mis = ws_disc.cell(d_row, 6, item.get("mis_val", 0.0))
        c_mis.number_format = '#,##0.00;(#,##0.00);"-"'
        c_mis.alignment = align_right
        
        c_bms = ws_disc.cell(d_row, 7, item.get("bms_val", 0.0))
        c_bms.number_format = '#,##0.00;(#,##0.00);"-"'
        c_bms.alignment = align_right
        
        c_diff = ws_disc.cell(d_row, 8, item.get("diff", 0.0))
        c_diff.number_format = '#,##0.00;(#,##0.00);"-"'
        c_diff.alignment = align_right
        c_diff.font = font_mismatch
        c_diff.fill = fill_mismatch
        
        for c in range(1, 9):
            ws_disc.cell(d_row, c).border = thin_border
            
        d_row += 1
        
    ws_disc.column_dimensions['A'].width = 6
    ws_disc.column_dimensions['B'].width = 12
    ws_disc.column_dimensions['C'].width = 45
    ws_disc.column_dimensions['D'].width = 30
    ws_disc.column_dimensions['E'].width = 10
    ws_disc.column_dimensions['F'].width = 20
    ws_disc.column_dimensions['G'].width = 20
    ws_disc.column_dimensions['H'].width = 20

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
