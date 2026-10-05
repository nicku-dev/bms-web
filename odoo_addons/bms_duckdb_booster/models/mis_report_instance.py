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
        
        # Build the iframe HTML
        # Ensure iframe takes full width and height
        iframe_html = f'''
        <div style="width: 100%; height: 80vh;">
            <iframe src="{bms_web_url}" width="100%" height="100%" frameborder="0" style="border: 0; min-height: 80vh;"></iframe>
        </div>
        '''
        
        wizard = self.env['bms.duckdb.preview.wizard'].create({
            'iframe_html': iframe_html
        })
        
        return {
            'name': 'BMS DuckDB Report Preview',
            'type': 'ir.actions.act_window',
            'res_model': 'bms.duckdb.preview.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
