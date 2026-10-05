import requests
from odoo import models, exceptions, _

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
        if not self.duckdb_boost_enabled:
            return super().compute()

        # Hardcoded for now. Can be moved to ir.config_parameter
        bms_web_url = self.env['ir.config_parameter'].sudo().get_param('bms_duckdb.url', 'http://10.100.1.58:3000')
        api_endpoint = f"{bms_web_url}/api/odoo/compute_booster"
        
        payload = {
            "odoo_report_instance_id": self.id,
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
