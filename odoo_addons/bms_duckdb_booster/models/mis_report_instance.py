import requests
from odoo import models, fields, exceptions, _

class MisReportInstance(models.Model):
    _inherit = 'mis.report.instance'

    duckdb_boost_enabled = fields.Boolean(
        string="DuckDB Boost Engine",
        default=True,
        help="If checked, matrix computation will be delegated to DuckDB (BMS-Web) for 1000x faster execution."
    )

    def action_compute_via_duckdb(self):
        """
        Preview using DuckDB. We ensure the flag is enabled.
        """
        self.ensure_one()
        self.duckdb_boost_enabled = True
        return self.preview()

    def export_xls(self):
        """
        Intercept Excel export to ensure DuckDB flag is enabled.
        """
        self.ensure_one()
        self.duckdb_boost_enabled = True
        return super().export_xls()

    def _compute_matrix(self):
        """
        Override the core MIS Builder _compute_matrix method.
        This allows both the Web Preview and Excel Export to magically use DuckDB.
        """
        self.ensure_one()
        if not getattr(self, 'duckdb_boost_enabled', False):
            return super()._compute_matrix()

        # Monkey patch mis_safe_eval to avoid ast.parse MemoryError
        import odoo.addons.mis_builder.models.mis_safe_eval as mse
        import odoo.addons.mis_builder.models.expression_evaluator as ee
        
        original_eval = mse.mis_safe_eval
        original_ee_eval = ee.mis_safe_eval
        
        mock_eval = lambda expr, locals_dict: 0.0
        mse.mis_safe_eval = mock_eval
        ee.mis_safe_eval = mock_eval

        # Monkey patch KpiMatrixRow.is_empty to avoid hiding rows
        import odoo.addons.mis_builder.models.kpimatrix as kpimatrix
        original_is_empty = kpimatrix.KpiMatrixRow.is_empty
        kpimatrix.KpiMatrixRow.is_empty = lambda self: False

        try:
            # Let Odoo build the empty KpiMatrix object
            matrix = super()._compute_matrix()

            # Convert matrix to dictionary for DuckDB while is_empty is still patched to False!
            # This ensures DuckDB receives all rows (except hide_always) regardless of them being 0.0 right now.
            skeleton_matrix = matrix.as_dict()

            # Hardcoded for now. Can be moved to ir.config_parameter
            bms_web_url = self.env['ir.config_parameter'].sudo().get_param('bms_duckdb.url', 'http://10.100.1.58:3000')
            api_endpoint = f"{bms_web_url}/api/odoo/compute_booster_direct"
            
            import odoo.tools.config as config
            payload = {
                "skeleton_json": skeleton_matrix,
                "target_db_name": self.env.cr.dbname,
                "report_name": self.name,
                "db_host": config['db_host'] or '10.100.1.58',
                "db_port": config['db_port'] or 5432,
                "db_user": config['db_user'],
                "db_password": config['db_password'],
            }
            
            import requests
            from odoo import exceptions, _
            try:
                response = requests.post(api_endpoint, json=payload, timeout=300)
                if response.status_code == 200:
                    compiled_matrix = response.json().get('data', {})
                else:
                    error_msg = response.json().get('detail', 'Unknown error') if response.headers.get('content-type') == 'application/json' else response.text
                    raise exceptions.UserError(_("DuckDB Native Compilation failed: %s") % error_msg)
            except requests.exceptions.RequestException as e:
                raise exceptions.UserError(_("Failed to connect to BMS-Web DuckDB Engine: \n%s") % str(e))
                
            try:
                from odoo.addons.mis_builder.models.accounting_none import AccountingNone
            except ImportError:
                AccountingNone = None

            compiled_body = compiled_matrix.get('body', [])
            comp_idx = 0
            
            for row in matrix.iter_rows():
                # Since is_empty() is patched to False, as_dict() above only skipped hide_always.
                # So we must perfectly align with it!
                if row.style_props.hide_always:
                    continue
                    
                if comp_idx < len(compiled_body):
                    comp_row = compiled_body[comp_idx]
                    compiled_cells = comp_row.get('cells', [])
                    for i, cell in enumerate(row.iter_cells()):
                        if i < len(compiled_cells):
                            comp_cell = compiled_cells[i]
                            if cell is not None and comp_cell:
                                val = comp_cell.get('val')
                                if val is None:
                                    cell.val = AccountingNone
                                else:
                                    try:
                                        cell.val = float(val) if val != "" else AccountingNone
                                    except ValueError:
                                        cell.val = AccountingNone
                                cell.val_rendered = comp_cell.get('val_formatted', '')
                    comp_idx += 1

        finally:
            # Revert monkey patches at the very end so Odoo's engine returns to normal!
            mse.mis_safe_eval = original_eval
            ee.mis_safe_eval = original_ee_eval
            kpimatrix.KpiMatrixRow.is_empty = original_is_empty

        return matrix
