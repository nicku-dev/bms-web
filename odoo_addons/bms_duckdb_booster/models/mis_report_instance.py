import requests
from odoo import models, exceptions, _

class MisReportInstance(models.Model):
    _inherit = 'mis.report.instance'

    def action_compute_via_duckdb(self):
        """
        Delegates the heavy matrix computation to the external DuckDB (bms-web) backend
        by redirecting the user to the BMS-Web frontend.
        """
        self.ensure_one()
        
        # Hardcoded for now. Can be moved to ir.config_parameter
        bms_web_url = self.env['ir.config_parameter'].sudo().get_param('bms_duckdb.url', 'http://10.100.1.58:3000')
        
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': bms_web_url,
        }
