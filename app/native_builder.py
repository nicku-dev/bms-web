import sqlite3
import os

class NativeSkeletonGenerator:
    def __init__(self, db_path, report_id, vessels, year):
        """
        :param db_path: Path to app_config.db
        :param report_id: ID of the report in bms_reports
        :param vessels: List of vessel names
        :param year: e.g. "2026"
        """
        self.db_path = db_path
        self.report_id = report_id
        self.vessels = vessels
        self.year = year
        self.quarters = [
            ("q1", f"{year}-01-01", f"{year}-03-31"),
            ("q2", f"{year}-04-01", f"{year}-06-30"),
            ("q3", f"{year}-07-01", f"{year}-09-30"),
            ("q4", f"{year}-10-01", f"{year}-12-31"),
            ("ytd", f"{year}-01-01", f"{year}-12-31"),
        ]

    def _fetch_rows(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Simple fetch ordered by sequence
        # For a full hierarchy we might need to build a tree, but a flat ordered list is fine for the JSON body
        cursor.execute('''
            SELECT * FROM bms_report_rows 
            WHERE report_id = ?
            ORDER BY sequence ASC, id ASC
        ''', (self.report_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def generate(self):
        cols = []
        # Generate Columns
        for vessel in self.vessels:
            for q, start_d, end_d in self.quarters:
                period_label = q.upper() if q != 'ytd' else 'YTD'
                cols.append({
                    "label": f"Kapal - {vessel} ({period_label} {self.year})",
                    "vessel_name": vessel,
                    "period": q,
                    "is_ytd": (q == "ytd")
                })
        
        # Default style logic based on Odoo
        def _get_style(r):
            style = []
            if r['row_type'] == 'header' or r['parent_id'] is None:
                style.append("font-weight: bold;")
                style.append("background-color: #E2EFDA;") # Light green
            if r['is_percentage']:
                style.append("font-style: italic;")
                style.append("color: #ff0000;")
            return " ".join(style)

        body = []
        rows = self._fetch_rows()
        for r in rows:
            var_name = r['variable_name']
            if not var_name:
                var_name = "dummy_var_" + str(r['id'])
                
            row_dict = {
                "label": r['label'],
                "name": var_name,
                "description": r['tag_name'] or '',
                "style": _get_style(r),
                "cells": []
            }
            
            # Generate cells
            for col in cols:
                q = col['period']
                val_c = ""
                
                if r['row_type'] == 'tag_query' and r['tag_name']:
                    # Generate the pseudo-Odoo domain so engine.py can parse it
                    if q == 'ytd':
                        start_d = f"{self.year}-01-01"
                        end_d = f"{self.year}-12-31"
                        val_c = f'{var_name}.{q} = balp[("tag_ids.name","=","{r["tag_name"]}")][(\'date\', \'>=\', \'{start_d}\'),(\'date\', \'<=\', \'{end_d}\')]'
                    else:
                        # Find the exact quarter dates
                        start_d = ""
                        end_d = ""
                        for tq, tsd, ted in self.quarters:
                            if tq == q:
                                start_d = tsd
                                end_d = ted
                                break
                        val_c = f'{var_name}.{q} = balp[("tag_ids.name","=","{r["tag_name"]}")][(\'date\', \'>=\', \'{start_d}\'),(\'date\', \'<=\', \'{end_d}\')]'
                        
                elif r['row_type'] == 'formula' and r['formula']:
                    # e.g. "pendapatan - biaya"
                    val_c = f"{var_name}.{q} = {r['formula']}"
                    
                elif r['row_type'] == 'header':
                    # Just an empty assignment to claim the variable with 0.0 (FastMatrixCompiler skips empty RHS ownership now!)
                    val_c = f"{var_name}.{q} = "

                # Add cell
                row_dict["cells"].append({
                    "val": 0.0,
                    "val_r": "-",
                    "val_c": val_c
                })
                
            body.append(row_dict)
            
        return {
            "cols": cols,
            "body": body
        }
