import io
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Header Styles
HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid") # Dark Slate
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)

THIN_BORDER = Border(
    left=Side(style='thin', color='E2E8F0'),
    right=Side(style='thin', color='E2E8F0'),
    top=Side(style='thin', color='E2E8F0'),
    bottom=Side(style='thin', color='E2E8F0')
)

def _sanitize_color(color_val: Any) -> Optional[str]:
    """Mengembalikan hex 6 karakter tanpa '#' jika valid, atau None."""
    if not color_val or not isinstance(color_val, str):
        return None
    s = color_val.strip().lstrip('#')
    if len(s) == 6 and all(c in '0123456789abcdefABCDEF' for c in s):
        return s.upper()
    return None

def _to_bool(val: Any) -> bool:
    """Mengubah berbagai variasi input menjadi boolean."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        v = val.strip().lower()
        return v in ("true", "1", "ya", "yes", "y", "t")
    return False

def export_single_template_excel(template_name: str, company_initial: str, company_name: str, config: dict) -> bytes:
    """
    Export single template ke format Excel (.xlsx) bergaya Odoo.
    Sheet 1: Baris Laporan (Rows)
    Sheet 2: Daftar Kapal (Vessels)
    Sheet 3: Info Template (Metadata)
    """
    wb = openpyxl.Workbook()
    
    # -------------------------------------------------------------
    # Sheet 1: Baris Laporan
    # -------------------------------------------------------------
    ws_rows = wb.active
    ws_rows.title = "Baris Laporan"
    ws_rows.views.sheetView[0].showGridLines = True
    
    row_headers = [
        ("No", 6, "center"),
        ("Kode Baris", 14, "center"),
        ("Tipe Baris", 13, "center"),
        ("Nama Baris / Label", 45, "left"),
        ("Formula / Query Odoo", 35, "left"),
        ("Auto Expand COA", 18, "center"),
        ("Level Indentasi", 15, "center"),
        ("Tebal", 10, "center"),
        ("Miring", 10, "center"),
        ("Sembunyikan", 14, "center"),
        ("Format %", 11, "center"),
        ("Warna Background", 18, "center"),
        ("ID Internal", 12, "center")
    ]
    
    # Tulis header
    for col_idx, (h_title, _, _) in enumerate(row_headers, start=1):
        cell = ws_rows.cell(row=1, column=col_idx, value=h_title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER
    ws_rows.row_dimensions[1].height = 28
    
    rows_data = config.get("rows", [])
    for row_idx, r in enumerate(rows_data, start=2):
        seq = row_idx - 1
        code = str(r.get("code") or f"R{seq}").strip()
        rtype = str(r.get("type") or "data").strip()
        label = str(r.get("label") or "").strip()
        expr = str(r.get("expression") or "").strip()
        auto_expand = "TRUE" if r.get("auto_expand_coa") else "FALSE"
        indent = int(r.get("indent_level") or 0)
        is_bold = "TRUE" if r.get("is_bold") else "FALSE"
        is_italic = "TRUE" if r.get("is_italic") else "FALSE"
        is_hidden = "TRUE" if r.get("is_hidden") else "FALSE"
        is_pct = "TRUE" if r.get("is_percentage") else "FALSE"
        bg_col = str(r.get("bg_color") or "").strip()
        internal_id = r.get("id") or seq
        
        row_values = [
            seq, code, rtype, label, expr, auto_expand,
            indent, is_bold, is_italic, is_hidden, is_pct,
            bg_col, internal_id
        ]
        
        # Color fill jika ada bg_color
        hex_clean = _sanitize_color(bg_col)
        row_fill = PatternFill(start_color=hex_clean, end_color=hex_clean, fill_type="solid") if hex_clean else None
        
        for col_idx, val in enumerate(row_values, start=1):
            cell = ws_rows.cell(row=row_idx, column=col_idx, value=val)
            _, _, col_align = row_headers[col_idx - 1]
            
            # Align & indent
            if col_idx == 4: # Nama Baris
                cell.alignment = Alignment(horizontal="left", vertical="center", indent=indent)
            else:
                cell.alignment = Alignment(horizontal=col_align, vertical="center")
                
            # Font
            cell_bold = (is_bold == "TRUE") or (col_idx == 2)
            cell_italic = (is_italic == "TRUE")
            cell.font = Font(name="Calibri", size=10, bold=cell_bold, italic=cell_italic)
            cell.border = THIN_BORDER
            
            if row_fill and col_idx not in (1, 13):
                cell.fill = row_fill
                
        ws_rows.row_dimensions[row_idx].height = 20
        
    for col_idx, (_, col_width, _) in enumerate(row_headers, start=1):
        col_letter = get_column_letter(col_idx)
        ws_rows.column_dimensions[col_letter].width = col_width
        
    ws_rows.freeze_panes = "A2"
    
    # -------------------------------------------------------------
    # Sheet 2: Daftar Kapal (Vessels)
    # -------------------------------------------------------------
    ws_vessels = wb.create_sheet(title="Daftar Kapal")
    ws_vessels.views.sheetView[0].showGridLines = True
    vessel_headers = [
        ("No", 6, "center"),
        ("ID Kapal (Odoo)", 16, "center"),
        ("Nama Kapal", 35, "left"),
        ("Pihak Ketiga", 16, "center")
    ]
    for col_idx, (h_title, _, _) in enumerate(vessel_headers, start=1):
        cell = ws_vessels.cell(row=1, column=col_idx, value=h_title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER
    ws_vessels.row_dimensions[1].height = 28
    
    vessels_data = config.get("vessels", [])
    for row_idx, v in enumerate(vessels_data, start=2):
        seq = row_idx - 1
        vid = v.get("id") or ""
        vname = str(v.get("name") or "").strip()
        is_third = "TRUE" if v.get("is_third_party") else "FALSE"
        
        row_values = [seq, vid, vname, is_third]
        for col_idx, val in enumerate(row_values, start=1):
            cell = ws_vessels.cell(row=row_idx, column=col_idx, value=val)
            _, _, col_align = vessel_headers[col_idx - 1]
            cell.alignment = Alignment(horizontal=col_align, vertical="center")
            cell.font = Font(name="Calibri", size=10)
            cell.border = THIN_BORDER
        ws_vessels.row_dimensions[row_idx].height = 20
        
    for col_idx, (_, col_width, _) in enumerate(vessel_headers, start=1):
        col_letter = get_column_letter(col_idx)
        ws_vessels.column_dimensions[col_letter].width = col_width
    ws_vessels.freeze_panes = "A2"

    # -------------------------------------------------------------
    # Sheet 3: Info Template (Metadata)
    # -------------------------------------------------------------
    ws_info = wb.create_sheet(title="Informasi Template")
    ws_info.views.sheetView[0].showGridLines = True
    info_headers = [("Parameter", 25, "left"), ("Nilai", 45, "left")]
    for col_idx, (h_title, _, _) in enumerate(info_headers, start=1):
        cell = ws_info.cell(row=1, column=col_idx, value=h_title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="left", vertical="center")
        cell.border = THIN_BORDER
    ws_info.row_dimensions[1].height = 28
    
    info_rows = [
        ("Nama Template", template_name),
        ("Inisial Perusahaan", company_initial),
        ("Nama Perusahaan", company_name),
        ("Total Baris", len(rows_data)),
        ("Total Kapal", len(vessels_data)),
        ("Waktu Export", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("Versi Format", "1.0 (Odoo Style Spreadsheet)")
    ]
    for row_idx, (param, val) in enumerate(info_rows, start=2):
        cell_p = ws_info.cell(row=row_idx, column=1, value=param)
        cell_v = ws_info.cell(row=row_idx, column=2, value=val)
        cell_p.font = Font(name="Calibri", size=10, bold=True)
        cell_p.border = THIN_BORDER
        cell_v.font = Font(name="Calibri", size=10)
        cell_v.border = THIN_BORDER
        ws_info.row_dimensions[row_idx].height = 20
        
    for col_idx, (_, col_width, _) in enumerate(info_headers, start=1):
        col_letter = get_column_letter(col_idx)
        ws_info.column_dimensions[col_letter].width = col_width

    # Simpan ke byte stream
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def export_all_templates_bundle_excel(templates_list: List[Dict[str, Any]], title_suffix: str = "Semua PT") -> bytes:
    """
    Export bundle semua template ke dalam satu file Excel multi-sheet.
    - Sheet 1: Ringkasan Semua Template
    - Sheet 2: Gabungan Semua Baris Laporan (dengan kolom Nama Template & Perusahaan)
    - Sheet 3: Gabungan Semua Kapal
    """
    wb = openpyxl.Workbook()
    
    # Sheet 1: Ringkasan
    ws_sum = wb.active
    ws_sum.title = "Daftar Template"
    ws_sum.views.sheetView[0].showGridLines = True
    
    sum_headers = [
        ("No", 6, "center"),
        ("Perusahaan", 15, "center"),
        ("Nama Template", 35, "left"),
        ("Jumlah Baris", 15, "center"),
        ("Jumlah Kapal", 15, "center")
    ]
    for col_idx, (h_title, _, _) in enumerate(sum_headers, start=1):
        cell = ws_sum.cell(row=1, column=col_idx, value=h_title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER
    ws_sum.row_dimensions[1].height = 28
    
    for row_idx, item in enumerate(templates_list, start=2):
        t_name = item.get("name", "Unnamed")
        comp = item.get("company_initial") or item.get("company_name") or "ALL"
        cfg = item.get("config", {})
        r_count = len(cfg.get("rows", []))
        v_count = len(cfg.get("vessels", []))
        
        vals = [row_idx - 1, comp, t_name, r_count, v_count]
        for col_idx, val in enumerate(vals, start=1):
            cell = ws_sum.cell(row=row_idx, column=col_idx, value=val)
            _, _, align = sum_headers[col_idx - 1]
            cell.alignment = Alignment(horizontal=align, vertical="center")
            cell.font = Font(name="Calibri", size=10, bold=(col_idx == 3))
            cell.border = THIN_BORDER
        ws_sum.row_dimensions[row_idx].height = 20
        
    for col_idx, (_, col_width, _) in enumerate(sum_headers, start=1):
        ws_sum.column_dimensions[get_column_letter(col_idx)].width = col_width
    ws_sum.freeze_panes = "A2"
    
    # Sheet 2: Semua Baris
    ws_rows = wb.create_sheet(title="Semua Baris Laporan")
    ws_rows.views.sheetView[0].showGridLines = True
    all_row_headers = [
        ("Nama Template", 30, "left"),
        ("Perusahaan", 14, "center"),
        ("No", 6, "center"),
        ("Kode Baris", 14, "center"),
        ("Tipe Baris", 13, "center"),
        ("Nama Baris / Label", 45, "left"),
        ("Formula / Query Odoo", 35, "left"),
        ("Auto Expand COA", 18, "center"),
        ("Level Indentasi", 15, "center"),
        ("Tebal", 10, "center"),
        ("Miring", 10, "center"),
        ("Sembunyikan", 14, "center"),
        ("Format %", 11, "center"),
        ("Warna Background", 18, "center"),
        ("ID Internal", 12, "center")
    ]
    for col_idx, (h_title, _, _) in enumerate(all_row_headers, start=1):
        cell = ws_rows.cell(row=1, column=col_idx, value=h_title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER
    ws_rows.row_dimensions[1].height = 28
    
    curr_row = 2
    for item in templates_list:
        t_name = item.get("name", "Unnamed")
        comp = item.get("company_initial") or "ALL"
        cfg = item.get("config", {})
        for seq, r in enumerate(cfg.get("rows", []), start=1):
            code = str(r.get("code") or f"R{seq}").strip()
            rtype = str(r.get("type") or "data").strip()
            label = str(r.get("label") or "").strip()
            expr = str(r.get("expression") or "").strip()
            auto_expand = "TRUE" if r.get("auto_expand_coa") else "FALSE"
            indent = int(r.get("indent_level") or 0)
            is_bold = "TRUE" if r.get("is_bold") else "FALSE"
            is_italic = "TRUE" if r.get("is_italic") else "FALSE"
            is_hidden = "TRUE" if r.get("is_hidden") else "FALSE"
            is_pct = "TRUE" if r.get("is_percentage") else "FALSE"
            bg_col = str(r.get("bg_color") or "").strip()
            internal_id = r.get("id") or seq
            
            vals = [
                t_name, comp, seq, code, rtype, label, expr,
                auto_expand, indent, is_bold, is_italic, is_hidden,
                is_pct, bg_col, internal_id
            ]
            
            hex_clean = _sanitize_color(bg_col)
            row_fill = PatternFill(start_color=hex_clean, end_color=hex_clean, fill_type="solid") if hex_clean else None
            
            for col_idx, val in enumerate(vals, start=1):
                cell = ws_rows.cell(row=curr_row, column=col_idx, value=val)
                _, _, align = all_row_headers[col_idx - 1]
                if col_idx == 6:
                    cell.alignment = Alignment(horizontal="left", vertical="center", indent=indent)
                else:
                    cell.alignment = Alignment(horizontal=align, vertical="center")
                cell.font = Font(name="Calibri", size=10, bold=(is_bold == "TRUE" or col_idx in (1, 4)), italic=(is_italic == "TRUE"))
                cell.border = THIN_BORDER
                if row_fill and col_idx not in (1, 2, 3, 15):
                    cell.fill = row_fill
            ws_rows.row_dimensions[curr_row].height = 20
            curr_row += 1
            
    for col_idx, (_, col_width, _) in enumerate(all_row_headers, start=1):
        ws_rows.column_dimensions[get_column_letter(col_idx)].width = col_width
    ws_rows.freeze_panes = "A2"
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def _is_header_row(cells, keywords: List[str], min_matches: int = 2) -> bool:
    if not cells:
        return False
    combined = " ".join(str(c).lower() for c in cells if c is not None)
    return sum(1 for kw in keywords if kw in combined) >= min_matches

def parse_template_excel(file_content: bytes) -> Dict[str, Any]:
    """
    Membaca dan mem-parsing file Excel (.xlsx) gaya Odoo.
    Mendukung fleksibilitas penamaan kolom (Bahasa Indonesia & English) dan multi-sheet.
    Mengembalikan dict berisi:
    {
        "template_name": str,
        "company_initial": str,
        "rows": List[dict],
        "vessels": List[dict],
        "is_bundle": bool,
        "bundled_templates": List[dict] (jika file berisi multi-template)
    }
    """
    wb = openpyxl.load_workbook(filename=io.BytesIO(file_content), data_only=True)
    sheet_names = wb.sheetnames
    
    # 1. Cek apakah ini file bundle ("Semua Baris Laporan" atau "Daftar Template")
    if "Semua Baris Laporan" in sheet_names:
        ws_sum = wb["Daftar Template"] if "Daftar Template" in sheet_names else None
        ws_ves = wb["Daftar Kapal"] if "Daftar Kapal" in sheet_names else None
        return _parse_bundle_sheet(wb["Semua Baris Laporan"], ws_summary=ws_sum, ws_vessels=ws_ves)
        
    # 2. Template Tunggal: Cari sheet Baris Laporan
    target_row_sheet = None
    for s_name in sheet_names:
        clean_s = s_name.strip().lower()
        if "baris" in clean_s or "row" in clean_s or "kpi" in clean_s or "laporan" in clean_s:
            target_row_sheet = wb[s_name]
            break
    if not target_row_sheet:
        # Fallback ke sheet pertama
        target_row_sheet = wb[sheet_names[0]]
        
    # 3. Baca Metadata dari Sheet 'Informasi Template' jika ada
    template_name = ""
    company_initial = ""
    company_name = ""
    
    for s_name in sheet_names:
        if "info" in s_name.strip().lower():
            ws_info = wb[s_name]
            for row in ws_info.iter_rows(values_only=True):
                if not row or len(row) < 2 or not row[0]:
                    continue
                k = str(row[0]).strip().lower()
                v = str(row[1]).strip() if row[1] is not None else ""
                if "nama template" in k or "template name" in k:
                    template_name = v
                elif "inisial" in k or "company initial" in k or "initial pt" in k:
                    company_initial = v
                elif "nama perusahaan" in k or "company name" in k:
                    company_name = v
            break

    # 4. Parse Baris Laporan
    rows_list = []
    headers = []
    
    all_sheet_rows = list(target_row_sheet.iter_rows(values_only=True))
    header_row_idx = 1
    row_keywords = ["kode", "code", "nama baris", "label", "formula", "tipe", "type", "expression"]
    
    for r_idx, row_cells in enumerate(all_sheet_rows, start=1):
        if _is_header_row(row_cells, row_keywords, min_matches=2):
            headers = [str(c).strip().lower() if c is not None else "" for c in row_cells]
            header_row_idx = r_idx
            break
            
    if not headers and all_sheet_rows:
        headers = [str(c).strip().lower() if c is not None else "" for c in all_sheet_rows[0]]
        header_row_idx = 1

    # Mapping nama kolom ke field standar
    col_map = {}
    for idx, h in enumerate(headers):
        if not h:
            continue
        if any(k in h for k in ["kode", "code"]):
            col_map["code"] = idx
        elif any(k in h for k in ["label", "nama baris", "nama", "keterangan"]):
            col_map["label"] = idx
        elif any(k in h for k in ["tipe", "type"]):
            col_map["type"] = idx
        elif any(k in h for k in ["formula", "expression", "rumus", "query"]):
            col_map["expression"] = idx
        elif any(k in h for k in ["auto_expand", "auto expand", "expand coa"]):
            col_map["auto_expand_coa"] = idx
        elif any(k in h for k in ["indent", "level"]):
            col_map["indent_level"] = idx
        elif any(k in h for k in ["tebal", "bold"]):
            col_map["is_bold"] = idx
        elif any(k in h for k in ["miring", "italic"]):
            col_map["is_italic"] = idx
        elif any(k in h for k in ["sembunyi", "hidden"]):
            col_map["is_hidden"] = idx
        elif any(k in h for k in ["persen", "percentage"]):
            col_map["is_percentage"] = idx
        elif any(k in h for k in ["warna", "bg_color", "color"]):
            col_map["bg_color"] = idx
        elif any(k in h for k in ["id internal", "id_internal"]):
            col_map["id"] = idx
        elif h == "id" and "code" in col_map and col_map["code"] != idx:
            col_map["id"] = idx

    # Iterasi baris data
    for row_cells in list(target_row_sheet.iter_rows(values_only=True))[header_row_idx:]:
        if not row_cells or all(c is None or str(c).strip() == "" for c in row_cells):
            continue
            
        def get_val(field: str, default: Any = "") -> Any:
            idx = col_map.get(field)
            if idx is not None and idx < len(row_cells):
                val = row_cells[idx]
                return val if val is not None else default
            return default

        label = str(get_val("label", "")).strip()
        code = str(get_val("code", "")).strip()
        expr = str(get_val("expression", "")).strip()
        
        # Jika label dan code kosong, lewati
        if not label and not code:
            continue
            
        raw_type = str(get_val("type", "data")).strip().lower()
        if raw_type in ("title", "judul", "header"):
            row_type = "title"
        elif raw_type in ("formula", "hitung", "calc"):
            row_type = "formula"
        elif raw_type in ("empty", "spasi", "blank"):
            row_type = "empty"
        else:
            row_type = "data"

        # Generate fallback code jika tidak diisi
        if not code:
            code = f"R{len(rows_list) + 1}"

        indent = 0
        try:
            indent = int(float(get_val("indent_level", 0)))
        except (ValueError, TypeError):
            pass
            
        internal_id = None
        try:
            val_id = get_val("id", None)
            if val_id is not None:
                internal_id = int(float(val_id))
        except (ValueError, TypeError):
            pass
        if internal_id is None:
            internal_id = len(rows_list) + 1

        bg_col = str(get_val("bg_color", "")).strip()
        if bg_col and not bg_col.startswith("#") and len(bg_col) == 6:
            bg_col = f"#{bg_col}"
        elif not bg_col or bg_col.lower() in ("none", "transparent", "null", "-"):
            bg_col = "transparent"

        row_obj = {
            "id": internal_id,
            "code": code,
            "type": row_type,
            "label": label,
            "expression": expr if row_type != "title" else "",
            "indent_level": indent,
            "is_bold": _to_bool(get_val("is_bold", False)),
            "is_italic": _to_bool(get_val("is_italic", False)),
            "is_hidden": _to_bool(get_val("is_hidden", False)),
            "is_percentage": _to_bool(get_val("is_percentage", False)),
            "bg_color": bg_col,
            "auto_expand_coa": _to_bool(get_val("auto_expand_coa", False))
        }
        rows_list.append(row_obj)

    # 5. Parse Daftar Kapal jika ada Sheet 'Daftar Kapal' / 'Vessels'
    vessels_list = []
    vessel_sheet = None
    for s_name in sheet_names:
        clean_s = s_name.strip().lower()
        if "kapal" in clean_s or "vessel" in clean_s:
            vessel_sheet = wb[s_name]
            break
            
    if vessel_sheet:
        v_headers = []
        v_header_idx = 1
        all_v_rows = list(vessel_sheet.iter_rows(values_only=True))
        for r_idx, row_cells in enumerate(all_v_rows, start=1):
            if _is_header_row(row_cells, ["kapal", "vessel", "pihak ketiga", "id"], min_matches=1):
                v_headers = [str(c).strip().lower() if c is not None else "" for c in row_cells]
                v_header_idx = r_idx
                break
                
        v_map = {}
        for idx, h in enumerate(v_headers):
            if any(k in h for k in ["id kapal", "id"]):
                v_map["id"] = idx
            elif any(k in h for k in ["nama kapal", "vessel", "nama"]):
                v_map["name"] = idx
            elif any(k in h for k in ["pihak ketiga", "third_party", "is_third_party"]):
                v_map["is_third_party"] = idx
                
        for row_cells in all_v_rows[v_header_idx:]:
            if not row_cells:
                continue
            v_name = ""
            if "name" in v_map and v_map["name"] < len(row_cells):
                v_name = str(row_cells[v_map["name"]] or "").strip()
            if not v_name:
                continue
            v_id = None
            if "id" in v_map and v_map["id"] < len(row_cells):
                try:
                    v_id = int(float(row_cells[v_map["id"]]))
                except (ValueError, TypeError):
                    pass
            is_3rd = False
            if "is_third_party" in v_map and v_map["is_third_party"] < len(row_cells):
                is_3rd = _to_bool(row_cells[v_map["is_third_party"]])
                
            vessels_list.append({
                "id": v_id,
                "name": v_name,
                "is_third_party": is_3rd
            })

    return {
        "is_bundle": False,
        "template_name": template_name,
        "company_initial": company_initial,
        "company_name": company_name,
        "rows": rows_list,
        "vessels": vessels_list
    }


def _parse_bundle_sheet(ws_rows, ws_summary=None, ws_vessels=None) -> Dict[str, Any]:
    """Parsing file Excel bundle yang berisi multi-template dalam satu sheet baris."""
    grouped: Dict[Tuple[str, str], List[dict]] = {}

    # Inisialisasi daftar template dari sheet summary jika ada
    if ws_summary:
        s_headers = []
        s_header_idx = 1
        all_s_rows = list(ws_summary.iter_rows(values_only=True))
        for r_idx, row_cells in enumerate(all_s_rows, start=1):
            if _is_header_row(row_cells, ["perusahaan", "template", "baris", "nama"], min_matches=1):
                s_headers = [str(c).strip().lower() if c is not None else "" for c in row_cells]
                s_header_idx = r_idx
                break
        s_map = {}
        for idx, h in enumerate(s_headers):
            if any(k in h for k in ["perusahaan", "company"]):
                s_map["company_initial"] = idx
            elif any(k in h for k in ["nama template", "template"]):
                s_map["template_name"] = idx
                
        for row_cells in all_s_rows[s_header_idx:]:
            if not row_cells:
                continue
            t_name = str(row_cells[s_map["template_name"]] or "").strip() if "template_name" in s_map and s_map["template_name"] < len(row_cells) else ""
            comp = str(row_cells[s_map["company_initial"]] or "").strip() if "company_initial" in s_map and s_map["company_initial"] < len(row_cells) else ""
            if t_name:
                grouped[(t_name, comp)] = []

    headers = []
    header_idx = 1
    all_b_rows = list(ws_rows.iter_rows(values_only=True))
    for r_idx, row_cells in enumerate(all_b_rows, start=1):
        if _is_header_row(row_cells, ["template", "kode", "label", "formula", "tipe"], min_matches=2):
            headers = [str(c).strip().lower() if c is not None else "" for c in row_cells]
            header_idx = r_idx
            break
            
    col_map = {}
    for idx, h in enumerate(headers):
        if any(k in h for k in ["nama template", "template"]):
            col_map["template_name"] = idx
        elif any(k in h for k in ["perusahaan", "company"]):
            col_map["company_initial"] = idx
        elif any(k in h for k in ["kode", "code"]):
            col_map["code"] = idx
        elif any(k in h for k in ["label", "nama baris", "nama"]):
            col_map["label"] = idx
        elif any(k in h for k in ["tipe", "type"]):
            col_map["type"] = idx
        elif any(k in h for k in ["formula", "expression", "rumus"]):
            col_map["expression"] = idx
        elif any(k in h for k in ["auto_expand", "auto expand"]):
            col_map["auto_expand_coa"] = idx
        elif any(k in h for k in ["indent"]):
            col_map["indent_level"] = idx
        elif any(k in h for k in ["tebal", "bold"]):
            col_map["is_bold"] = idx
        elif any(k in h for k in ["miring", "italic"]):
            col_map["is_italic"] = idx
        elif any(k in h for k in ["sembunyi", "hidden"]):
            col_map["is_hidden"] = idx
        elif any(k in h for k in ["persen", "percentage"]):
            col_map["is_percentage"] = idx
        elif any(k in h for k in ["warna", "bg_color"]):
            col_map["bg_color"] = idx
        elif any(k in h for k in ["id internal", "id_internal"]):
            col_map["id"] = idx

    # Kelompokkan baris berdasarkan (template_name, company_initial)
    for row_cells in list(ws_rows.iter_rows(values_only=True))[header_idx:]:
        if not row_cells or all(c is None or str(c).strip() == "" for c in row_cells):
            continue
            
        def get_val(field: str, default: Any = "") -> Any:
            idx = col_map.get(field)
            if idx is not None and idx < len(row_cells):
                val = row_cells[idx]
                return val if val is not None else default
            return default

        t_name = str(get_val("template_name", "Template Default")).strip()
        comp = str(get_val("company_initial", "")).strip()
        label = str(get_val("label", "")).strip()
        code = str(get_val("code", "")).strip()
        expr = str(get_val("expression", "")).strip()
        
        if not label and not code:
            continue
            
        raw_type = str(get_val("type", "data")).strip().lower()
        if raw_type in ("title", "judul"):
            row_type = "title"
        elif raw_type in ("formula", "hitung"):
            row_type = "formula"
        elif raw_type in ("empty", "spasi"):
            row_type = "empty"
        else:
            row_type = "data"

        key = (t_name, comp)
        if key not in grouped:
            grouped[key] = []
            
        indent = 0
        try:
            indent = int(float(get_val("indent_level", 0)))
        except (ValueError, TypeError):
            pass
            
        bg_col = str(get_val("bg_color", "")).strip()
        if bg_col and not bg_col.startswith("#") and len(bg_col) == 6:
            bg_col = f"#{bg_col}"
        elif not bg_col or bg_col.lower() in ("none", "transparent", "null", "-"):
            bg_col = "transparent"

        grouped[key].append({
            "id": len(grouped[key]) + 1,
            "code": code or f"R{len(grouped[key]) + 1}",
            "type": row_type,
            "label": label,
            "expression": expr if row_type != "title" else "",
            "indent_level": indent,
            "is_bold": _to_bool(get_val("is_bold", False)),
            "is_italic": _to_bool(get_val("is_italic", False)),
            "is_hidden": _to_bool(get_val("is_hidden", False)),
            "is_percentage": _to_bool(get_val("is_percentage", False)),
            "bg_color": bg_col,
            "auto_expand_coa": _to_bool(get_val("auto_expand_coa", False))
        })

    bundled_list = []
    for (t_name, comp), rows in grouped.items():
        bundled_list.append({
            "name": t_name,
            "company_initial": comp,
            "config": {
                "rows": rows,
                "vessels": []
            }
        })

    return {
        "is_bundle": True,
        "bundled_templates": bundled_list,
        "count": len(bundled_list)
    }
