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

    def compute(self):
        """
        Override the core MIS Builder compute method.
        Instead of running slow PostgreSQL queries and Python math,
        we fetch the pre-compiled JSON dictionary from DuckDB (BMS-Web).
        """
        self.ensure_one()
        if not getattr(self, 'duckdb_boost_enabled', False):
            return super().compute()
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
            # This is now OOM-proof because python eval is disabled!
            # We let Postgres query the move lines so that account details are populated!
            skeleton_matrix = super().compute()
        finally:
            # Revert monkey patches
            mse.mis_safe_eval = original_eval
            ee.mis_safe_eval = original_ee_eval
            kpimatrix.KpiMatrixRow.is_empty = original_is_empty

        # Hardcoded for now. Can be moved to ir.config_parameter
        bms_web_url = self.env['ir.config_parameter'].sudo().get_param('bms_duckdb.url', 'http://10.100.1.58:3000')
        api_endpoint = f"{bms_web_url}/api/odoo/compute_booster_direct"
        
        import odoo.tools.config as config
        payload = {
            "skeleton_json": skeleton_matrix,
            "target_db_name": self.env.cr.dbname,
            "report_name": self.name,
            "db_host": config['db_host'] or '10.100.1.58', # Fallback to server IP if local
            "db_port": config['db_port'] or 5432,
            "db_user": config['db_user'],
            "db_password": config['db_password'],
        }
        
        import requests
        try:
            response = requests.post(api_endpoint, json=payload, timeout=30)
            if response.status_code == 200:
                result_data = response.json()
                # Inject notes if any (following standard Odoo behavior)
                result_data["notes"] = self.get_notes_by_cell_id()
                return result_data
            else:
                error_msg = response.json().get('detail', 'Unknown error')
                raise exceptions.UserError(_("DuckDB Native Compilation failed: %s") % error_msg)
                
        except requests.exceptions.RequestException as e:
            raise exceptions.UserError(_("Failed to connect to BMS-Web DuckDB Engine: \n%s") % str(e))
