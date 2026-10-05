import requests
from odoo import models, exceptions, _

class MisReportInstance(models.Model):
    _inherit = 'mis.report.instance'

    def action_compute_via_duckdb(self):
        """
        Delegates the heavy matrix computation to the external DuckDB (bms-web) backend
        instead of relying on Odoo's slow ORM.
        """
        self.ensure_one()
        
        # Hardcoded for now. Can be moved to ir.config_parameter
        bms_web_url = "http://127.0.0.1:3000" 
        api_endpoint = f"{bms_web_url}/api/compile_report"
        
        # We pass minimal necessary arguments. 
        # BMS-web will pull the skeleton_json directly from the database and compile.
        payload = {
            "odoo_report_instance_id": self.id,
            "report_name": self.name,
        }
        
        try:
            # We add a slight timeout to prevent blocking if bms-web is down
            response = requests.post(api_endpoint, json=payload, timeout=15)
            
            if response.status_code == 200:
                result_data = response.json()
                
                # In a real implementation, you would store or render this result.
                # For this module's initial version, we notify the user.
                # Alternatively, we could return a URL action that opens the BMS Web interface directly.
                bms_url = f"{bms_web_url}/report/{self.id}"
                
                return {
                    'type': 'ir.actions.act_url',
                    'target': 'new',
                    'url': bms_url,
                }
            else:
                error_msg = response.json().get('detail', 'Unknown error')
                raise exceptions.UserError(_("DuckDB Compilation failed: %s") % error_msg)
                
        except requests.exceptions.RequestException as e:
            raise exceptions.UserError(_("Failed to connect to BMS-Web DuckDB Engine: \n%s") % str(e))
